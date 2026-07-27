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
Geometrie rechnet Code, nie das Modell. Ohne Netz, ohne Konto und ohne KI
bleibt alles außer dem Chat benutzbar.

---

## Harte Regeln

Jede hat einen Test. Ein Verstoß ist ein roter Lauf, keine Geschmacksfrage.

**Aufbau**
1. **Kein Qt unterhalb von `ui/`.** `core` ohne installiertes Qt importierbar.
2. **Keine Geometrieänderung außerhalb einer Op** — auch nicht „kurz" im
   Viewport, auch nicht im Agenten.
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
11. **Kein OpenSCAD-Lauf ohne Quelltextprüfung** (§32) — auch bei
    LLM-Quelltext.
12. **Keine absoluten Pfade** in Projektdateien.
13. **Eigene Bausteine reisen nie in Projektdateien mit** (§24.5).
    Ausführbarer Code kommt aus der Installation und dem Nutzerordner, nie
    aus einer geöffneten Datei.
14. **Kennzahlen aus Schichtanalyse und G-Code werden nie vermischt** —
    Herkunft immer ausweisen (§22.5).
15. **Keine GPL-Abhängigkeit.** Kein `pymeshlab`, kein `PyQt`. OpenSCAD und
    Slicer nur extern aufrufen, nie mitliefern.

**Bedienung**
16. **Jeder Agentenvorschlag ist genau eine Transaktion.** Ein Undo nimmt ihn
    vollständig zurück.
17. **Jede Ausnahme trägt mindestens einen Handlungsvorschlag.** Ein Fehler
    endet nie mit „fehlgeschlagen".
18. **Keine Bedeutung allein über Farbe.** Immer eine zweite Kodierung.
19. **Keine Bestätigungsdialoge vor rücknehmbaren Handlungen.**
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
| Docstrings, Kommentare, Commits | Englisch |
| Schlüssel in Projektdatei und Schemata | Englisch |
| Oberflächentexte | Deutsch + Englisch über `tr()` |
| Doku und Bauplan | Deutsch |

Begriffszuordnung (verbindlich): Op → `Operation`, Transaktion →
`Transaction`, Baustein → `Part`, Steckbrief → `digest`, Prüfbericht →
`report`, Passung → `Fit`, Provenienz → `provenance`, Profil → `Profile`,
Regelsammlung → `rules`. Neue Begriffe zuerst in Bauplan §4.2, dann in den
Code.

---

## Paketstruktur

```
app/
  core/        # kein Qt, keine Fenster, keine Benutzerinteraktion
    types.py errors.py units.py
    registry/ scene/ geom/ slice/ ingest/ perceive/ knowledge/
    agent/ backends/ export/
  ui/          # PySide6 — darf core benutzen, nie umgekehrt
  cli/         # Kommandozeilen-Einstieg auf core
  i18n/
  tests/data/  # Referenzkorpus
```

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
8. Texte übersetzbar, deutsch und englisch

## Checkliste: neuer Baustein

1. `@register_part(...)` mit `params`, `features`, `preview`, `doc`
2. Umsetzung gegen `manifold3d` — **nicht** OpenSCAD
3. Benannte Features zurückgeben (Provenienz-IDs)
4. `to_scad()` für den Quelltext-Export
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

## Checkliste: Regelsammlung ändern

1. Eintrag unter `core/knowledge/rules/` mit Datum und Anlass
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
| Bausteinversion | geänderter Baustein wird beim Öffnen gemeldet |
| Schichtanalyse | Kennzahlen gegen analytische Körper, Inselerkennung |
| Parameter | Grammatik, Zyklen, Ablehnung |
| Passungen | Verletzung wird erkannt |
| Migrationen | alte Beispieldateien öffnen |
| Zuordnung | ID-Stabilität, Mehrdeutigkeit |
| Fehler | jede Ausnahme mit Handlungsvorschlag |
| Barrierefreiheit | keine Bedeutung allein über Farbe |
| Leistung | Zielwerte Bauplan §31, Regressionsschwelle 25 % |
| Lizenzen | Abhängigkeiten gegen Freigabeliste |
| Hauptwege | die drei Wege aus Bauplan §2.2 Ende zu Ende |
| Agenten-Suite | 30 Referenzanfragen |

---

## Was NICHT gebaut wird

Web-Anwendung im Browser, Mehrbenutzerbetrieb, Cloud-Ablage von Projekten,
Plugin-System, Telemetrie, Verzweigungen im Op-Stack, Verrundungen auf
Mesh-Kanten vor dem B-Rep-Kern, Bearbeitung im gehosteten Backend,
Betriebsarten-Umschaltung in der Oberfläche, **eigener G-Code-Slicer**
(Schichtanalyse ja, G-Code nein — §22).

Wenn eine Aufgabe eines dieser Dinge zu verlangen scheint, ist die Aufgabe
falsch verstanden — nachfragen statt bauen.
