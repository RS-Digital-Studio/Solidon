# AGENTS.md — Repository-Regeln

Immer lesen. Der Bauplan (`3d-agent-bauplan.md`) sagt **was**, diese Datei
sagt **wie**, `ROADMAP.md` sagt **was als Nächstes**. Bei Widerspruch gilt der
Bauplan.

---

## Projekt in fünf Zeilen

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

Jede hat einen Test. Ein Verstoß ist ein roter Lauf, keine Geschmacksfrage.

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
    Sprachmodells. Seit dem Ausbau von OpenSCAD (26.08.2026) gibt es keinen
    Weg mehr dorthin; die Regel steht jetzt als Sperre: Wer einen neuen baut,
    baut die Prüfung mit.
12. **Keine absoluten Pfade** in Projektdateien.
13. **Ausführbarer Code reist nie in einer Projektdatei mit** (§24.5). Er
    kommt aus der Installation und dem Nutzerordner, nie aus einer geöffneten
    Datei — ein eigener Baustein als `.py` bleibt deshalb, wo er liegt. Ein
    Baustein als **Rezept** darf mitreisen (Entscheidung Robert, 24.08.2026):
    Er ist eine Liste registrierter Operationen mit Werten, führt also nichts
    aus, was eine Projektdatei nicht ohnehin auslöst. **Seit dem Ausbau von
    OpenSCAD (26.08.2026) steht das ohne Vorbehalt.** Vorher konnte ein Wert
    selbst Quelltext sein — `create_from_scad` trug ihn im Parameter
    `source` —, und die Erlaubnis hielt nur zusammen mit Regel 11. Diese
    Öffnung gibt es nicht mehr: Eine Projektdatei trägt Operationen und Werte,
    und keiner davon wird ausgeführt. `scene/foreign.py` weist fremde Herkunft
    weiterhin aus (§32) — nicht mehr, weil etwas laufen könnte, sondern weil
    der Nutzer wissen soll, woher der Inhalt stammt.
14. **Kennzahlen aus Schichtanalyse und G-Code werden nie vermischt** —
    Herkunft immer ausweisen (§22.5).
15. **Keine GPL-Abhängigkeit.** Kein `pymeshlab`, kein `PyQt`. Einen Slicer
    nur extern aufrufen, nie mitliefern.

**Bedienung**
16. **Jeder Agentenvorschlag ist genau eine Transaktion.** Ein Undo nimmt ihn
    vollständig zurück.
17. **Jede Ausnahme trägt mindestens einen Handlungsvorschlag.** Ein Fehler
    endet nie mit „fehlgeschlagen".
18. **Keine Bedeutung allein über Farbe.** Immer eine zweite Kodierung.
19. **Keine Bestätigungsdialoge vor rücknehmbaren Handlungen.** Einzige
    ausdrücklich gewünschte Ausnahme: Vor dem Löschen von Verlaufsschritten
    nennt eine Nachfrage auch abhängige Schritte und den Rückweg über Strg+Z.
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

**Deutsch heißt echte Umlaute** — ä ö ü ß, nie `ae`/`oe`/`ue`/`ss` als Ersatz.
Das gilt für jeden deutschen Text hier: Docstrings, Kommentare,
Commit-Meldungen, Doku und die deutsche Quelle der Oberflächentexte.

Eine **weitere Sprache** ist eine Datei in `app/i18n/locales/` und sonst
nichts: Sprachauswahl, Einsammler, Handbuch, Abbildungen und Prüfung lesen das
Verzeichnis (`available_languages()`). Unvollständig eingecheckt wird keine —
`tests/test_translations.py` prüft jede gefundene Datei, nicht nur die
englische. Derzeit sind es sechs: Deutsch als Quelle, dazu `en`, `es`, `fr`,
`it` und `pt`.

Kommentare und Docstrings waren bis dahin englisch. Sie sind es nicht mehr:
`app/`, `tests/` und `tools/` sind vollständig übersetzt. Was neu dazukommt,
wird deutsch geschrieben — nachträglich zu übersetzen gibt es nichts mehr.

**Assert-Meldungen in Tests fallen nicht darunter.** Sie stehen neben dem
Bezeichner, den sie erklären, und der ist englisch; zweisprachige Sätze mitten
im Testcode lesen sich schlechter, nicht besser. Wer eine neue schreibt, hält
sich an den Bestand der Datei.

**Und die Bezeichnerregel gilt `app/` und `tools/`, nicht `tests/`.** Der Grund
ist die **Auslieferung**: `app/` reist zum Kunden, `tools/` baut das Paket —
dort steht Code, den jemand liest, der das Projekt nicht kennt. `tests/` liest
nur, wer hier arbeitet, und hier wird deutsch geschrieben.
`tests/test_language_rules.py` prüft deshalb genau diese beiden Verzeichnisse.

**Ausgenommen heißt nicht egal, sondern: am Bestand der Datei orientieren** —
dieselbe Regel wie für die Assert-Meldungen darüber. Sonst spricht in einem
Jahr jede Datei ihre eigene Sprache, und das wäre schlechter als beide
Einzelentscheidungen. (Gezählt am 23.08.2026: 78 deutsche Bezeichner in 27
Testdateien, 37 verschiedene Namen. Sie werden nicht umbenannt — eine
Massenänderung in fremden Dateien kostet mehr, als sie einbringt.)

**Was die Prüfung leistet und was nicht:** `GERMAN_STEMS` ist eine **kuratierte
Liste**, keine Sprachprüfung. Der automatische Weg ist am 23.08.2026 gemessen
gescheitert — eine aus den deutschen Kommentaren gewonnene Liste meldete 2758
angebliche Verstöße, darunter `index`, `material`, `parameter` und `value`.
Deutsch und Englisch überlappen bei technischen Wörtern zu stark. **Wer ein
deutsches Wort in einem Bezeichner findet, trägt seinen Stamm dort ein**; der
Test fängt, was schon einmal jemand falsch gemacht hat.

Begriffszuordnung (verbindlich): Op → `Operation`, Transaktion →
`Transaction`, Baustein → `Part`, Steckbrief → `digest`, Prüfbericht →
`report`, Passung → `Fit`, Provenienz → `provenance`, Profil → `Profile`,
Regelsammlung → `rules`. Neue Begriffe zuerst in Bauplan §4.2, dann in den
Code.

---

## Paketstruktur

Was wo liegt und warum, steht in der Karte in `CLAUDE.md` — hier steht nur, was
daraus folgt.

Kommunikation aus dem Kern nach außen nur über den `OpContext`:
`ctx.progress`, `ctx.ask`, `ctx.cancelled` — keine globalen Objekte, keine
Dialoge.

---

## Arbeitsweise

- **Kleine Schritte.** Nach jedem Schritt läuft die vollständige Suite. Ein
  Schritt, der sie rot lässt, wird nicht auf den nächsten gestapelt.
- **Test zuerst bei Geometrie.** Erst die erwarteten Kennzahlen gegen eine
  Datei aus `tests/data/`, dann die Umsetzung.
- **Eine Phase gilt als fertig**, wenn ihre Abnahmekriterien aus Bauplan §40
  grün sind — nicht wenn sie sich vollständig anfühlt.
- **Konsistenz vor Vollständigkeit.** Acht Ops, die überall identisch
  auftauchen, schlagen zwanzig, die auseinanderdriften.
- **Neue Fehlerbilder werden Testdateien**, keine Sonderfälle im Code.
- **Bestehende Struktur nutzen.** Vor einer neuen Datei prüfen, ob die Sache in
  ein vorhandenes Modul gehört.

---

## Checkliste: neue Operation

1. `@register_op(...)` mit `name`, `title`, `category`, `params`,
   `reversible`, `consumes`/`produces`, `applies_to`, `deterministic`, `doc`,
   optional `shortcut`
2. Parameterschema mit Grenzen, Einheiten, Vorgaben und Zuordnung zu Vorder-
   oder Rückseite des Dialogs
3. Umsetzung als `OpFn` gegen `manifold3d` / `trimesh`; Boolesche Ops über die
   Rückfallkette, verwendete Stufe in `solver`
4. Bei Zufall: Startwert aus `ctx.seed`, `deterministic=False`
5. Beide Qualitätsstufen bedienen (`ctx.quality`)
6. Befunde als `findings` zurückgeben, nicht selbst protokollieren
7. Geometrietest gegen den Korpus
8. Texte übersetzbar — deutsche Quelle, und jeder Katalog aus
   `app/i18n/locales/` zieht nach

## Checkliste: neuer Baustein

1. `@register_part(...)` mit `params`, `features`, `preview`, `doc`
2. Umsetzung gegen `manifold3d`
3. Benannte Features zurückgeben (Provenienz-IDs)
4. `to_scad()` für den Quelltext-Export — **das bleibt.** Es schreibt eine
   Datei und führt nichts aus; mit dem Ausbau von OpenSCAD (26.08.2026) ist
   der *Lauf* verschwunden, nicht das Format
5. Test über den gesamten Parameterbereich: wasserdicht, Mindestwandstärke,
   keine Selbstdurchdringung an den Grenzen
6. Normteilmaße aus der Tabelle, nie im Baustein hart eintragen
7. Vorschaubild wird gerendert, nicht von Hand gepflegt
8. Bei Maßänderung an einem bestehenden Baustein: `parts_version` erhöhen und
   Änderungsverlauf ergänzen (§24.4)

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

1. Eintrag in `core/knowledge/data/rules.toml` mit Datum und Anlass
2. Version erhöhen
3. Agenten-Suite vorher und nachher, beide Ergebnisse festhalten
4. Verschlechtert sich die Quote, wird die Regel zurückgenommen — nicht
   „trotzdem behalten"

---

## Testarten

| Art | Prüft |
|---|---|
| Kerntrennung | `core` ohne Qt importierbar |
| Sprachregelung | keine deutschen Stämme in Bezeichnern |
| Registerkonsistenz | jede Op vollständig, Kürzel eindeutig, Startwert wo nötig |
| Auswertung | zweimal = identisch; Objektzahländerung hält an |
| Geometrie | Kennzahlen je Op gegen den Korpus |
| Rückfallkette | jede Stufe einmal erzwungen |
| Determinismus | gleicher Startwert → gleiches Ergebnis |
| Bausteine | Parameterbereich, Vorschaubild |
| Bausteindatei | lokaler Export/Import als verlustfreie Rundreise, Metadaten, Größen-/Integritätsgrenzen, kein Code und kein Netz |
| Bausteinversion | geänderter Baustein wird beim Öffnen gemeldet |
| Schichtanalyse | Kennzahlen gegen analytische Körper, Inselerkennung |
| Parameter | Grammatik, Zyklen, Ablehnung |
| Passungen | Verletzung wird erkannt |
| Migrationen | alte Beispieldateien öffnen |
| Zuordnung | ID-Stabilität, Mehrdeutigkeit |
| Fehler | jede Ausnahme mit Handlungsvorschlag |
| Barrierefreiheit | keine Bedeutung allein über Farbe |
| Oberflächengrenzen | höchstens neun Menüs, zwölf Zeilen je Menü, acht Werkzeuge, acht Felder vorn |
| Leistung | Zielwerte Bauplan §31, Regressionsschwelle 25 % |
| Lizenzen | Abhängigkeiten gegen Freigabeliste |
| Hauptwege | die vier Wege aus Bauplan §2.2 Ende zu Ende |
| Anschluss | was nur an einer Stelle eingelöst wird, wird an dieser Stelle geprüft — nicht „der Cache kann es", sondern „die Anwendung tut es" |
| Doku-Karte | jedes Verzeichnis mit Code trägt eine `CLAUDE.md`, jeder §-Verweis darin trifft |
| Agenten-Suite | 39 Referenzanfragen |

---

## Was NICHT gebaut wird

Web-Anwendung im Browser, Mehrbenutzerbetrieb, Cloud-Ablage von Projekten,
gehostete Tauschbörse, Plugin-System, Telemetrie, Verzweigungen im Op-Stack,
Verrundungen auf Mesh-Kanten vor dem B-Rep-Kern, Bearbeitung im gehosteten
Backend, Betriebsarten-Umschaltung in der Oberfläche, **eigener G-Code-Slicer**
(Schichtanalyse ja, G-Code nein — §22). Der lokale Baustein-Export und -Import
per Datei bleibt ausdrücklich erhalten (§24.5).

Wenn eine Aufgabe eines dieser Dinge zu verlangen scheint, ist die Aufgabe
falsch verstanden — nachfragen statt bauen.
