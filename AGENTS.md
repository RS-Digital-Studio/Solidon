# AGENTS.md — Repository-Regeln

Immer lesen. Diese Datei sagt, **wie** gearbeitet wird; welche Unterlage
welche andere Frage beantwortet, steht in `CLAUDE.md`. Bei Widerspruch gilt
der Bauplan (`3d-agent-bauplan.md`).

---

## Projekt in Kürze

Desktop-Anwendung zum Konstruieren, Generieren und Bearbeiten druckbarer
3D-Modelle. Kern ist ein non-destruktiver Operationsstack über einer Szene mit
mehreren Objekten, benannten Projektparametern und Passungsbeziehungen. Ein
LLM-Agent steuert denselben Operations-API fern, den auch die Menüs benutzen.
Geometrie rechnet Code, nie das Modell. Nach der einmaligen
Gerätefreischaltung bleibt Solidon ohne Netz und ohne Konto vollständig
nutzbar; ein Arbeitsrechner ohne Netz wird per Dateiweg über ein zweites Gerät
aktiviert. Ohne KI bleibt nur der Chat aus.

---

## Harte Regeln

Wo die Suite eine Regel hält, ist ein Verstoß ein roter Lauf, keine
Geschmacksfrage. Über den ganzen Baum wachen Tests bei 1, 3, 4, 9–13, 15–20
und 22; bei 2, 6, 7, 14 und 21 prüfen sie die Stellen, an denen die Regel
greift. 5 und 8 sind Urteilsfragen ohne mechanische Prüfung — sie hält die
Durchsicht (`/regelcheck`, Agent `solidon3d-review`).

**Aufbau**
1. **Kein Qt unterhalb von `ui/`.** `core` ohne installiertes Qt importierbar.
2. **Keine Geometrieänderung außerhalb einer Op** — auch nicht „kurz" im
   Viewport, auch nicht im Agenten. Eine Op darf beliebig viele Nutzergesten
   zu einem Schritt zusammenfassen, wenn sie **vollständig aus ihren
   Parametern reproduzierbar** ist: Ein Editor sammelt Gesten in einen
   Parameterwert, das Ergebnis entsteht erst bei der Auswertung. Was der
   Editor zeigt, während er offen ist, ist eine Vorschau und kein
   Dokumentzustand.
3. **`OpContext.scene` ist nur lesend.** Ops erzeugen Objekte, sie ändern
   keine.
4. **Keine Op ohne Registereintrag**, Parameterschema, Geometrietest und
   übersetzte Texte.
5. **Verträge zuerst.** Signaturen aus Bauplan §9 stehen fest, bevor ein Modul
   entsteht.

**Zahlen**
6. **Der Kern rechnet in Millimetern und doppelter Genauigkeit.** Gerundet wird
   nur in der Anzeige. Fließkommavergleich nie mit `==`.
7. **Keine Zahlenkonstante für Toleranzen** — Verweis ins Materialprofil
   (`auto:<material>`).
8. **Keine Streuzahl, wo ein Projektparameter passt.**
9. **Jede randomisierte Prozedur führt einen gespeicherten Startwert** und ist
   als `deterministic=False` markiert.

**Sicherheit**
10. **Kein `eval`** — Parameterausdrücke über den eigenen Auswerter.
11. **Kein fremder Quelltext wird ausgeführt** (§32) — auch nicht der eines
    Sprachmodells. Einen Weg dorthin gibt es nicht; wer einen baut, baut die
    Prüfung mit.
12. **Keine absoluten Pfade** in Projektdateien.
13. **Ausführbarer Code reist nie in einer Projektdatei mit** (§24.5). Er
    kommt aus der Installation und dem Nutzerordner, nie aus einer geöffneten
    Datei — ein eigener Baustein als `.py` bleibt, wo er liegt. Ein Baustein
    als **Rezept** darf mitreisen (Entscheidung Robert): eine Liste
    registrierter Operationen mit Werten, von denen keiner ausgeführt wird.
    `scene/foreign.py` weist fremde Herkunft aus (§32), damit der Nutzer
    weiß, woher der Inhalt stammt.
14. **Kennzahlen aus Schichtanalyse und G-Code werden nie vermischt** —
    Herkunft immer ausweisen (§22.5).
15. **Keine GPL-Abhängigkeit.** Kein `pymeshlab`, kein `PyQt`. Einen Slicer
    nur extern aufrufen, nie mitliefern. Die bereits freigegebene GCC-Laufzeit
    in Ziel-Wheels ist ausschließlich mit dem vollständigen SPDX-Paar
    `GPL-3.0-or-later WITH GCC-exception-3.1` aus `licences.toml/allowed_with`
    zulässig (§36). Ebenso eng zugelassen ist der unveränderte
    PyInstaller-Bootloader unter `GPL-2.0-or-later WITH PyInstaller Bootloader
    Exception` (Entscheidung Robert, §36). Das ist keine allgemeine Freigabe
    für GPL-Code oder andere Linking-Ausnahmen; die konkrete Laufzeit muss die
    Ausnahme tragen und deren Bedingungen erfüllen.

**Bedienung**
16. **Jeder Agentenvorschlag ist genau eine Transaktion.** Ein Undo nimmt ihn
    vollständig zurück.
17. **Jede Ausnahme trägt mindestens einen Handlungsvorschlag.** Ein Fehler
    endet nie mit „fehlgeschlagen".
18. **Keine Bedeutung allein über Farbe.** Immer eine zweite Kodierung.
19. **Keine Bestätigungsdialoge vor rücknehmbaren Handlungen.** Ausdrücklich
    gewünschte Ausnahmen: Vor dem Löschen von Verlaufsschritten nennt eine
    Nachfrage auch abhängige Schritte und den Rückweg über Strg+Z. Beim Import
    oberhalb der automatischen Merkmalsgrenze wird die lange Vollerkennung mit
    Zeitschätzung angeboten; ohne Zustimmung lädt das Modell mit begrenzter
    Erkennung weiter (§21.1).
20. **Keine fest eingebaute Zeichenkette** in der Oberfläche — alles über
    `tr()`.

**Haltung**
21. **Nie stillschweigend raten.** Mehrdeutigkeit hält an und fragt — über
    `ctx.ask`, nie über einen Dialog aus dem Kern heraus.
22. **Keine neue Abhängigkeit** ohne Eintrag in der Lizenzliste.

---

## Sprachregelung

| Bereich | Sprache |
|---|---|
| Bezeichner, Dateinamen, Modulnamen | Englisch |
| Docstrings, Kommentare, Commits | **Deutsch** |
| Schlüssel in Projektdatei und Schemata | Englisch |
| Oberflächentexte | Deutsche Quelle, je Sprache ein Katalog über `tr()` |
| Doku und Bauplan | Deutsch |

**Deutsch heißt echte Umlaute** — ä ö ü ß, nie `ae`/`oe`/`ue`/`ss` als Ersatz,
in jedem deutschen Text: Docstrings, Kommentare, Commits, Doku und die
deutsche Quelle der Oberflächentexte. Geprüft werden Commit-Meldungen
(`.githooks/commit-msg`) und die Oberflächentexte
(`tests/test_translations.py`); Docstrings und Kommentare prüft kein Wächter.

Eine **weitere Sprache** ist eine Datei in `app/i18n/locales/` und sonst
nichts: Sprachauswahl, Einsammler, Handbuch, Abbildungen und Prüfung lesen das
Verzeichnis (`available_languages()`). Unvollständig eingecheckt wird keine —
`tests/test_translations.py` prüft jede gefundene Datei. Derzeit sind es
sechs: Deutsch als Quelle, dazu `en`, `es`, `fr`, `it` und `pt`.

**Die Bezeichnerregel gilt `app/` und `tools/`**, weil beide ausgeliefert
werden bzw. das Paket bauen; `tests/test_language_rules.py` prüft genau diese
zwei. In `tests/` — auch für Assert-Meldungen — gilt der Bestand der jeweiligen
Datei: Keine Datei spricht zwei Sprachen, und fremde Dateien werden nicht
massenhaft umbenannt.

`GERMAN_STEMS` ist eine **kuratierte Liste**, keine Sprachprüfung — Deutsch und
Englisch überlappen bei technischen Wörtern zu stark für eine automatische.
**Wer ein deutsches Wort in einem Bezeichner findet, trägt seinen Stamm dort
ein.**

Begriffe und ihre Bezeichner stehen verbindlich in Bauplan §4.2; ein neuer
Begriff kommt zuerst dorthin, dann in den Code.

---

## Paketstruktur

Was wo liegt, steht in den Karten (`CLAUDE.md` an der Wurzel und je
Verzeichnis), das Warum in `konzepte/begruendungen/`.

Agenten ohne Claude Codes automatische Bereichsladung lesen vor einer Änderung
die `CLAUDE.md`-Karten vom Root bis zum betroffenen Verzeichnis und jede Datei
unter `.claude/rules/`, deren `paths:`-Muster auf die geänderte Datei passt.
Diese Dateien bleiben die gemeinsame Quelle für Claude Code und Codex.

Projekterfahrungen liegen unter `.claude/memory/` — **nur auf der jeweiligen
Maschine**, nicht versioniert. Vor einer Änderung über `MEMORY.md` nach
einschlägigen Themen suchen und nur diese lesen. Zugangsdaten oder Schlüssel
von dort werden nie in Agentenkonfigurationen kopiert.

Kommunikation aus dem Kern nach außen nur über den `OpContext`:
`ctx.progress`, `ctx.ask`, `ctx.cancelled` — keine globalen Objekte, keine
Dialoge.

---

## Arbeitsweise

- **Mehr liefern, wo es geht.** Eine selbst gesetzte Grenze, die dem Kunden
  weniger gibt (Größen, Formen, Bereiche), wird gehoben, sobald sie nicht nötig
  ist. Jede gefundene Leistungs- oder Speicherverbesserung wird umgesetzt,
  solange das Ergebnis **druckgleich** bleibt (Bauplan §11.2; Messung vorher
  und nachher, Test); Schleifen je Element werden dabei als Feldrechnung
  gebündelt, nach den Plattformregeln in `kern.md`. Das gilt in jeder Sitzung und für jeden Agenten auch
  für Funde unterwegs: im eigenen Gebiet gleich umsetzen, sonst als neuer
  Punkt melden.
- **Kleine Schritte, je Schritt nur die betroffenen Tests**
  (`tools/affected_tests.py` leitet sie aus dem Importgraphen ab), auf Paket-
  und Fixzweigen auch vor dem Commit, dazu ruff, format, mypy. Das
  Entwicklungstor — alle Tests ohne Fenster, Renderer und Leistung — läuft
  einmal **vor jedem Stand, der nach main geht**: vor dem Merge und vor jedem
  Commit direkt auf main, den `post-commit` sofort pusht (Entscheidung
  Robert). Ein Schritt, der
  seine Tests rot lässt, wird nicht auf den nächsten gestapelt.
- **Fenster, Renderer und Leistung lokal nur beim Release**; der Push nach main
  löst im öffentlichen Repository alle Prüfungen selbst aus — Kern und
  Renderer auf allen vier Plattformen, dazu die betroffenen Fenster- und
  Slicertests (`/liefern`). Auf Zweigen läuft keine CI (Entscheidung Robert).
  Ein grüner Entwicklungslauf ersetzt sie nicht.
- **Bilder und Handbuch nur beim Release — und nur, was sich geändert hat**
  (Weg in `/erzeugen`).
- **Die CI-Aufteilung hat einen geprüften Vertrag**
  (`konzepte/konzept-ci-testlaufzeiten-2026-09.md`, Wächter in
  `tests/test_packaging.py` und `tests/test_ci_runner.py`).
- **Test zuerst bei Geometrie.** Erst die erwarteten Kennzahlen gegen eine
  Datei aus `tests/data/`, dann die Umsetzung.
- **Eine Phase gilt als fertig**, wenn ihre Abnahmekriterien aus Bauplan §40
  grün sind — nicht wenn sie sich vollständig anfühlt.
- **Konsistenz vor Vollständigkeit.** Acht Ops, die überall identisch
  auftauchen, schlagen zwanzig, die auseinanderdriften.
- **Kein Revert.** Nie `checkout`/`restore`/`reset --hard`/`clean` über Arbeit
  — vorwärts fixen; an diesem Baum arbeiten oft mehrere Sitzungen zugleich.
  Rebase, Force-Push und History-Rewrite nur nach Rückfrage. Kein Hook fragt
  oder sperrt vor einem Befehl (Entscheidung Robert); die Regel gilt trotzdem.
- **Claude und Codex bleiben gleich** (Entscheidung Robert): Agenten, Skills,
  Hooks, Plugins und Umgebung sind auf beiden Seiten dieselben, und jede
  Änderung geht auf beide. `tests/test_agent_mirror.py` hält es fest.
- **Neue Fehlerbilder werden Testdateien**, keine Sonderfälle im Code.
- **Bestehende Struktur nutzen.** Vor einer neuen Datei prüfen, ob die Sache in
  ein vorhandenes Modul gehört.

---

## Checkliste: neue Operation

1. `@register_op(...)` mit `name`, `title`, `category`, `params`,
   `reversible`, `consumes`/`produces`, `applies_to`, `deterministic`, `doc`,
   optional `shortcut` und `icon` (sonst trägt die Kategorie das Symbol;
   Einzelheiten und die volle Signatur: `/neue-op`)
2. Parameterschema mit Grenzen, Einheiten, Vorgaben und Zuordnung zu Vorder-
   oder Rückseite des Dialogs — vorn höchstens vier Felder zugleich, bei neun
   von zehn Operationen höchstens drei (`tests/test_interface_limits.py`)
3. Umsetzung als `OpFn` gegen `manifold3d` / `trimesh`; Boolesche Ops über die
   Rückfallkette, verwendete Stufe in `solver`
4. Bei Zufall: Startwert aus `ctx.seed`, `deterministic=False`
5. Beide Qualitätsstufen bedienen (`ctx.quality`)
6. Befunde als `findings` zurückgeben, nicht selbst protokollieren
7. Geometrietest gegen den Korpus
8. Texte übersetzbar — deutsche Quelle, und jeder Katalog aus
   `app/i18n/locales/` zieht nach

## Checkliste: neuer Baustein

1. `@register_part(...)` mit `name`, `title`, `group`, `params`, `features`,
   `doc` (Einzelheiten und die volle Signatur: `/neuer-baustein`)
2. Umsetzung gegen `manifold3d`
3. Benannte Features zurückgeben (Provenienz-IDs)
4. `to_scad()` für den Quelltext-Export — es schreibt eine Datei und führt
   nichts aus
5. Bereichsnachweis, wenn der Baustein oder seine Grenzen sich ändern —
   wasserdicht, Mindestwandstärke, keine Selbstdurchdringung an den Ecken des
   Parameterbereichs: `.venv\Scripts\python.exe tools/check_part_ranges.py
   <name>` schreibt ihn nach `app/core/knowledge/data/part_ranges.toml`. Die
   Suite fährt den Bereich nicht, sie vergleicht nur, ob der Nachweis zum
   Stand passt (Entscheidung Robert); die Prüflogik selbst steht in
   `test_parts.py`
6. Normteilmaße aus der Tabelle, nie im Baustein hart eintragen
7. Vorschaubild wird gerendert (`parts/preview.py`), nicht von Hand gepflegt
8. Bei Maßänderung an einem bestehenden Baustein: `LIBRARY_VERSION` erhöhen,
   am Baustein einen `PartChange` in `changes=` ergänzen und danach
   `tools/make_examples.py` fahren (§24.4)

## Checkliste: Dateiformat ändern

1. `format_version` erhöhen
2. Migrationsfunktion `vN→vN+1`
3. Beispieldatei der alten Version einchecken
4. Test: alte Datei öffnet und rechnet korrekt
5. Ältere Migrationen bleiben bestehen, werden nie zusammengefasst

## Checkliste: neue Abhängigkeit

1. Lizenz feststellen, in die Freigabeliste eintragen
2. Bei GPL: nicht verwenden — Alternative oder externer Aufruf
3. Hinweis im Über-Dialog, wenn die Lizenz das verlangt
4. Lizenzprüfung muss grün bleiben
5. Untergrenze in `pyproject.toml`, **feste Version in `constraints.txt`** —
   sonst installiert der nächste Klon etwas anderes als die CI. Prüfen mit
   `python tools/check_env.py`

## Checkliste: Regelsammlung ändern

1. Eintrag in `app/core/knowledge/data/rules.toml` mit Datum und Anlass
2. Version erhöhen
3. Agenten-Suite vorher und nachher, beide Ergebnisse festhalten
4. Verschlechtert sich die Quote, wird die Regel zurückgenommen — nicht
   „trotzdem behalten"

---

## Testarten

Welche Datei welche Art trägt, steht in `tests/CLAUDE.md`.

| Art | Prüft |
|---|---|
| Kerntrennung | `core` ohne Qt importierbar |
| Sprachregelung | keine deutschen Stämme in Bezeichnern |
| Registerkonsistenz | jede Op vollständig, Kürzel eindeutig, Startwert wo nötig |
| Auswertung | zweimal = identisch; Objektzahländerung hält an |
| Geometrie | Kennzahlen je Op gegen den Korpus |
| Rückfallkette | jede Stufe einmal erzwungen |
| Determinismus | gleicher Startwert → gleiches Ergebnis |
| Bausteine | Vorschaubild, versprochene Merkmale, Prüflogik des Parameterbereichs — nicht ihr Lauf über jeden Baustein |
| Bausteinversion | geänderter Baustein wird beim Öffnen gemeldet |
| Schichtanalyse | Kennzahlen gegen analytische Körper, Inselerkennung |
| Parameter | Grammatik, Zyklen, Ablehnung |
| Passungen | Verletzung wird erkannt |
| Migrationen | alte Beispieldateien öffnen |
| Zuordnung | ID-Stabilität, Mehrdeutigkeit |
| Fehler | jede Ausnahme mit Handlungsvorschlag |
| Barrierefreiheit | keine Bedeutung allein über Farbe |
| Oberflächengrenzen | höchstens neun Menüs, zwölf Zeilen je Menü, acht Umschalter, vier Felder vorn |
| Leistung | Zielwerte Bauplan §31, Regressionsschwelle 25 % |
| Lizenzen | Abhängigkeiten gegen Freigabeliste |
| Hauptwege | die vier Wege aus Bauplan §2.2 Ende zu Ende |
| Anschluss | was nur an einer Stelle eingelöst wird, wird an dieser Stelle geprüft — nicht „der Cache kann es", sondern „die Anwendung tut es" |
| Doku-Karte | jedes Verzeichnis mit Code trägt eine `CLAUDE.md`, jeder §-Verweis darin trifft |
| Agenten-Suite | 39 Referenzanfragen |

---

## Was NICHT gebaut wird

Web-Anwendung im Browser, Mehrbenutzerbetrieb, Cloud-Ablage von Projekten,
Plugin-System, Telemetrie, Verzweigungen im Op-Stack, Bearbeitung im
gehosteten Backend, Betriebsarten-Umschaltung in der Oberfläche, **eigener
G-Code-Slicer** (Schichtanalyse ja, G-Code nein — §22).

Verrunden und Fase an Netzkanten sind kein Nicht-Ziel: Beide Körperarten
nehmen sie an (Bauplan §25, Regeln in `.claude/rules/kanten.md`).

Wenn eine Aufgabe eines dieser Dinge zu verlangen scheint, ist die Aufgabe
falsch verstanden — nachfragen statt bauen.
