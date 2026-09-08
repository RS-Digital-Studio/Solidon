# Solidon — Bauplan v12

Desktop-Anwendung zum **Konstruieren, Generieren und Bearbeiten** druckbarer
3D-Modelle. Non-destruktiver Operationsstack über einer Szene mit mehreren
Objekten, vollwertiger Viewport, Bausteinbibliothek, Rückkopplung aus Slicer
und Drucker. Veröffentlichung als Download; nach Gerätefreischaltung lokal
ohne Netz nutzbar. Aktivierung, Aktualisierung, Support und optionale
KI-Backends haben ausdrücklich begrenzte Netzwege (§5, §27, §37).

Spezifikation zur Abarbeitung durch einen Programmier-Agenten.
Begleitdateien: `AGENTS.md` (Repository-Regeln, immer lesen) und `ROADMAP.md`
(aktuelle Aufgaben und Phasenstand).

> **Wenn du nur drei Kapitel liest:** §1 Leitprinzipien, §2 Bedienkonzept,
> §9 Kernverträge. Das erste sagt, wonach entschieden wird, das zweite wofür,
> das dritte womit.

---

## Inhalt

**Warum und wofür** — §1 Leitprinzipien · §2 Bedienkonzept · §3
Ausführungsmodell · §4 Glossar und Sprachregelung · §5 Verteilungsmodell ·
§6 Die drei Säulen

**Aufbau** — §7 Schichten · §8 Paketstruktur · §9 Kernverträge · §10
Operationsregister · §11 Zahlen und Determinismus

**Datenmodell** — §12 Szenenmodell · §13 Projektparameter · §14 Passungen ·
§15 Auswertung · §16 Projektdatei · §17 Eingangsstufe und Rückfallketten

**Oberfläche** — §18 Viewport · §19 Bedienung und Barrierefreiheit · §20 Farbe

**Analyse und Agent** — §21 Feature-Erkennung · §22 Schichtanalyse · §23
Steckbrief · §24 Bausteinbibliothek · §25 Operationskatalog · §26
Agentenschicht · §27 Backends

**Ausgabe** — §28 Slicer-Rückkopplung · §29 Export · §30 B-Rep-Kern

**Qualität** — §31 Leistungsbudget · §32 Sicherheit · §33 Fehler und
Protokollierung · §34 Referenzdaten · §35 Testbarkeit · §36 Lizenzen · §37
Veröffentlichung und Auflagen · §38 Desktop-Spezifika · §39 Regelsammlung

**Umsetzung** — §40 Phasen · §41 Ausbaustufen · §42 Grenzen · §43 Nächster
Schritt

---

## 0. Stand und Geltung

Dieser Bauplan beschreibt die verbindlichen Produktverträge. Er ist keine
zweite Arbeitsliste: Erreichter Umfang, Prioritäten und noch fehlende Abnahmen
stehen in `ROADMAP.md`; frühere Messungen und Entscheidungen mit ihrem
damaligen Stand in `ROADMAP-ARCHIV.md`.

Eine Abweichung im Code hebt eine Anforderung nicht auf. Ist sie nicht durch
eine dokumentierte Produktentscheidung ersetzt, bleibt sie als konkrete
Aufgabe in der Roadmap bestehen. Vorhandene Implementierung und bestandene
Abnahme sind dabei getrennt zu belegen (§40).

Die Paragraphnummern bleiben für Verweise aus Code und Dokumentation stabil.
Typen, Register und Dateischema haben ihre ausführbare Quelle in den jeweils
genannten Modulen; Änderungen daran ziehen die betroffenen Verträge und
Beispiele hier nach. Ein Beispielwert ist keine Aussage über die neueste
veröffentlichte Version.

---


## 1. Leitprinzipien

Neun Sätze, an denen jede Entscheidung gemessen wird.

1. **Jede Operation ist manuell bedienbar.** Die KI ruft exakt dieselben
   Funktionen wie ein Menüeintrag.
2. **Non-destruktiv.** Nie Geometrie überschreiben, sondern den
   Operationsstack fortschreiben.
3. **Alles genau einmal deklariert.** Ops, Bausteine, Profile, Texte haben je
   eine Quelle; alle Oberflächen werden daraus erzeugt.
4. **Reproduzierbar.** Gleiche Datei, gleiche Bibliotheksversionen, gleiches
   Ergebnis. Zufall bekommt einen gespeicherten Startwert.
5. **Die KI erzeugt niemals Koordinaten.** Sie verweist auf erkannte Features,
   benutzt Projektparameter und setzt geprüfte Bausteine ein.
6. **Nie stillschweigend raten** — weder die Zuordnung noch der Agent. Bei
   Mehrdeutigkeit wird angehalten und gefragt.
7. **Deterministische Geometrie, probabilistische Absicht.** Das LLM
   interpretiert die Anfrage. Die Geometrie rechnet Code.
8. **Nach einmaliger Gerätefreischaltung vollständig ohne Konto und ohne Netz
   nutzbar.** Die Freischaltung geht direkt oder per Anfrage- und Antwortdatei
   über ein zweites Gerät; danach sind gehostete Dienste Bequemlichkeit, nie
   Betriebsvoraussetzung.
9. **Der Kern kennt keine Oberfläche.** Keine Qt-Einbindung unterhalb von
   `ui`. Alles Rechnende ist ohne Fenster aufrufbar.

---

## 2. Bedienkonzept

Solidon richtet sich an Menschen ohne CAD-Kenntnisse, die druckbare Modelle
konstruieren, erzeugen oder vor dem Slicer vorbereiten möchten. Die Oberfläche
bleibt einfach: Vielseitigkeit gehört in die Tiefe, nicht an die Oberfläche.

### 2.1 Das Versprechen

**Geometrieänderungen bleiben rücknehmbar.** Jede Geometrieänderung entsteht
als Op im Operationsstack; ihre Parameter bleiben nachträglich änderbar.
Kamera, Auswahl und Darstellung ändern das Dokument nicht. Das ist der eigentliche Gewinn des
non-destruktiven Aufbaus — und er muss spürbar sein, nicht bloß vorhanden.
Praktisch heißt das: keine Bestätigungsdialoge vor rücknehmbaren Handlungen,
kein „Möchten Sie wirklich", keine Sackgassen. Die ausdrücklich gewünschte
Ausnahme ist das Löschen eines Verlaufsschritts: Die Nachfrage nennt die
Folge und Strg+Z, besonders wenn abhängige Schritte mit betroffen sind.

### 2.2 Vier Hauptwege

Alles Weitere ist Ausbau dieser vier. Sie müssen ohne Handbuch gehen.

**Weg 1 — Fremdes Modell anpassen** (der häufigste Fall)
Datei ziehen und ablegen → Einheitenrückfrage, falls nötig → Modell steht,
Prüfbericht sichtbar → Fläche oder Bohrung anklicken → im Chat sagen, was
werden soll, oder aus dem Kontextmenü wählen → Vorschau als
Vorher/Nachher → übernehmen → exportieren.

**Weg 2 — Neu konstruieren**
Neues Projekt → Grundformen, Bausteine oder Skizzen wählen, oder dem Agenten
beschreiben, was gebraucht wird → Projektparameter und Operationen anlegen →
Parameterleiste zeigt die Hauptmaße → Maße ändern und Vorschau prüfen →
exportieren.

**Weg 3 — Generieren**
Text oder Bild → Mesh → Reparaturkette läuft automatisch → Prüfbericht →
gegebenenfalls teilen und verstiften → exportieren.

**Weg 4 — Organisch formen**
Grundkörper grob zusammensetzen → weich verschmelzen → gleichmäßig vernetzen →
von Hand ausformen, Skelett setzen und stellen → Prüfbericht → exportieren.

Der Weg für Formen, die sich nicht bemaßen lassen. Was ihn von den anderen
dreien unterscheidet: Hier zählt eine Geste und keine Zahl — und deshalb
gilt Regel 2 hier besonders scharf. Ein Editor sammelt die Gesten in einen
Parameterwert, und das Ergebnis entsteht erst bei der Auswertung; was während
des Formens im Bild steht, ist Vorschau und kein Dokumentzustand.

Diese vier Wege sind je ein Beispielprojekt (§37) und je eine
Abnahmeprüfung (§40).

### 2.3 Die ersten fünf Minuten

- **Kein leerer Startbildschirm.** Zuletzt geöffnete Projekte, ein großes
  Ablagefeld sowie je ein Einstiegsbeispiel für die vier Hauptwege. Weitere
  Beispiele stehen getrennt von diesen Einstiegen.
- **Ziehen und Ablegen funktioniert überall** — auf das Fenster, auf den
  Viewport, auf den Objektbaum.
- **Die Erstinbetriebnahme fragt das Nötigste**: Sprache und Drucker.
  Erkannte Slicer-Filamente werden mit ihren vorhandenen Angaben übernommen;
  ein nicht zugeordneter Typ bleibt ausdrücklich unbekannt. Keine zweite
  Materialfrage und keine stillschweigende PLA-Zuordnung. Zusatzprogramme
  und Chat-Zugang bleiben optional. Die Einrichtung ist überspringbar und
  jederzeit nachholbar.
- **Ohne KI-Zugang läuft alles außer dem Chat.** Kein Nörgeln, kein
  Werbebanner — ein Hinweis an der Chatleiste, mehr nicht.

### 2.4 Gestufte Tiefe

Jeder Dialog hat eine kurze Vorderseite und einen aufklappbaren Bereich
„Weitere Einstellungen". Vorn stehen die zwei bis drei Werte, die man
tatsächlich ändert; hinten Toleranzen, Auflösungen, Rückfallverhalten.

Die Vorgaben kommen aus dem Drucker- und Materialprofil und sind so gewählt,
dass die Vorderseite in den meisten Fällen genügt. **Eine gute Vorgabe ist
mehr wert als eine gute Einstellmöglichkeit.**

### 2.5 Fensterschema

Die 3D-Ansicht füllt die verfügbare Arbeitsfläche. Kompakte Karten liegen
darüber; das Auswahlfenster kann daneben angedockt oder frei platziert werden.
Leere oder zugeklappte Bereiche geben ihren Platz frei.

- **Links über der Ansicht:** einklappbare Abschnitte für Objekte,
  Projektparameter, Verlauf und Filamente; Filamente sind anfangs zugeklappt.
- **Rechts über der Ansicht:** eine Karte mit Reitern für Prüfbericht und Chat,
  bei Bedarf zusätzlich Tour oder Skizzenbedingungen. Fehler und Warnungen
  tragen einen sichtbaren Zähler. Bei Warnungen oder Fehlern wechselt die
  sichtbare Karte zum Prüfbericht; eine laufende Tour behält bei normalen
  Warnungen Vorrang. Hält die Auswertung an, kommt der Prüfbericht auch vor
  einer laufenden Tour nach vorn. Eine bewusst ausgeblendete Karte bleibt
  verborgen; der Warnungszähler in der Statusleiste führt zum Bericht zurück.
- **Auswahlfenster:** Maße und passende Handlungen des gewählten Körpers oder
  Merkmals stehen gemeinsam an einem Ort. Das Fenster öffnet sich bei der
  ersten Auswahl; bewusstes Schließen gilt bis zum Wechsel der Auswahl.
  Es ist verschiebbar, an beiden Seiten andockbar und in niedrigen Fenstern
  vollständig über einen Rollbereich bedienbar.
- **Unten über der Ansicht:** Werkzeugleiste und die zum offenen Werkzeug
  gehörenden Bedienelemente. Die Statusleiste nennt Auswahl, Maße, Fortschritt
  und Warnungen.
- **F9 blendet die Bericht-/Chatkarte ein oder aus.** Ein Warnungszähler in der
  Statusleiste führt auch bei ausgeblendeter Karte zum Prüfbericht zurück.
- Keine Betriebsarten-Umschaltung zwischen „Bearbeiten“ und „Konstruieren“.
  Alle Werkzeuge arbeiten an derselben Szene.

### 2.6 Entdeckbarkeit

- **Befehlspalette** über eine Taste: alles aus dem Register per Suche
  erreichbar, mit Kürzel daneben — so lernt man die Kürzel nebenbei.
- **Kontextmenü am Feature**: Klick auf eine Bohrung bietet genau die Ops an,
  die auf Bohrungen anwendbar sind. Der kürzeste Weg vom Sehen zum Tun.
- **Bausteinkatalog mit Vorschaubildern** statt einer Namensliste. Eine
  Bibliothek, die man nicht sieht, existiert für den Nutzer nicht.
- **Der Chat ist auch ein Suchfeld.** „Wie mache ich das Loch größer?"
  beantwortet der Agent mit dem Vorschlag *und* dem Hinweis, wo die Funktion
  im Menü steht.

### 2.7 Fehler als Vorschlag

Ein Fehler endet nie mit „fehlgeschlagen". Er nennt in dieser Reihenfolge:
was nicht ging, warum, was jetzt möglich ist — mit anklickbaren
Handlungen.

> Die Differenz ist fehlgeschlagen, weil das Modell an drei Stellen offen ist.
> **[Reparieren und erneut versuchen]  [Stellen zeigen]  [Abbrechen]**

Kein Stapelabzug im Nutzerdialog. Der gehört ins Protokoll und in den
Fehlerbericht (§33).

### 2.8 Rückmeldung und Wartezeit

- Unter 0,2 s: nichts anzeigen
- Bis 2 s: Mauszeiger und Statusleiste
- Darüber: Fortschritt in der Statusleiste mit **Abbrechen**, Oberfläche
  bedienbar
- Über 10 s: zusätzlich eine Schätzung, wenn möglich

Die letzte gültige Darstellung bleibt sichtbar (§15.3) — nie ein leerer
Viewport, nie ein blockierendes Fenster.

### 2.9 Maus und Navigation

Vorgabe ist Solidons eigene Steuerung: Die linke Taste verschiebt beim Ziehen
und wählt beim Klicken, die rechte dreht um den Mittelpunkt der Ansicht, das
gedrückte Rad kippt nach oben und unten, das gescrollte Rad zoomt auf den
Mauszeiger. Dazu fliegen W, A, S und D durch die Szene, Q und E kippen sie.
Der Flug nimmt den Blickpunkt mit — anders als der Zoom, der bis vor das Teil
fährt und dort stehen bleibt.

Bis zum 03.09.2026 stand hier die Slicer-Gewohnheit als Vorgabe; Robert hat
sie an diesem Tag umgelegt („eine eigene und Standard wählen"). Sie ist nicht
verschwunden, sondern eines von vier Alternativschemata, die Fremdprogramme
nachbilden und in den Einstellungen stehen: Cura (links wählt, rechts dreht,
Umschalt und Ziehen schiebt), Bambu Studio/Orca/PrusaSlicer (links dreht),
CAD-typisch (mittlere Taste dreht, rechts zoomt) und Blender-typisch. Das
kostet fast nichts und erspart Umgewöhnung.

Die Tastatursteuerung gilt nur in der eigenen Vorgabe. In einer Nachbildung
wäre sie eine Bewegung, die das Vorbild nicht kennt — und in Blender sind die
Tasten belegt.

---

## 3. Ausführungsmodell

Der Plan wird von einem Programmier-Agenten umgesetzt. Zeitaufwand ist kein
Kriterium; Eindeutigkeit und maschinelle Abnahme sind es.

- **Abnahmekriterien statt Zeitschätzungen.** Jede Phase in §40 endet mit
  Bedingungen, die grün sein müssen.
- **Tests sind die Definition von fertig.** Für jede Geometrieoperation
  existiert ein Test mit festem Eingangs-Mesh (§34) und erwarteten Kennzahlen.
- **Kleine Schritte.** Nach jedem Schritt laufen die von der Änderung
  betroffenen Tests. Das vollständige Tor aus getrennter Suite, Leistung,
  Ruff, Formatierung und mypy gehört vor den Commit; der verbindliche Ablauf
  steht in `AGENTS.md` und dem Skill `/pruefen`.
- **Verbote sind Prüfungen, keine Absichten.** Jede harte Regel aus
  `AGENTS.md` hat einen Test.
- **Verträge zuerst.** Bei jedem neuen Modul steht die Signatur aus §9 fest,
  bevor die Umsetzung beginnt.
- **Konsistenz vor Vollständigkeit.** Acht Ops, die überall identisch
  auftauchen, schlagen zwanzig, die auseinanderdriften.
- **Keine stillen Erweiterungen.** Neue Abhängigkeiten, Ops, Formatversionen
  und Parameterfunktionen sind an Checklisten in `AGENTS.md` gebunden.

---

## 4. Glossar und Sprachregelung

### 4.1 Sprachen

| Bereich | Sprache |
|---|---|
| Bezeichner im Code, Dateinamen, Modulnamen | Englisch |
| Docstrings und Kommentare | **Deutsch** |
| Schlüssel in Projektdatei und Schemata | Englisch |
| Oberflächentexte | deutsche Quelle, je Sprache ein Katalog über `tr()` |
| Doku für Nutzer | deutsche Quelle, Sprachfassungen wie die Oberfläche |
| Dieser Bauplan und interne Projektdoku | Deutsch |
| Commit-Nachrichten | **Deutsch** |

Bezeichner in `app/` und `tools/` werden gegen eine kuratierte Liste deutscher
Stämme geprüft. Sie ist keine allgemeine Spracherkennung. In `tests/` folgen
Bezeichner und Assert-Meldungen dem Bestand der jeweiligen Datei; deutsche
Docstrings und Kommentare verwenden überall echte Umlaute.

Docstrings und Kommentare standen hier bis „Doku nachziehen" (b2e6e28) auf
Englisch. Die Zeile ist geändert, weil die Trennung nicht zwischen Code und
Prosa verläuft, sondern zwischen **Maschine und Mensch**: Bezeichner liest der
Interpreter, Kommentare liest nur Robert. `app/`, `tests/` und `tools/` sind
vollständig nachgezogen; die Prüfung bleibt auf Bezeichner beschränkt, weil nur
die eindeutig entscheidbar ist.

**Aus „Deutsch und Englisch" sind sechs Sprachen geworden**, und die Zeile in
der Tabelle nennt deshalb keine mehr: Deutsch ist die Quelle im Code, unter
`app/i18n/locales/` liegt je Sprache eine Datei — derzeit `en`, `es`, `fr`,
`it` und `pt`. Eine weitere Sprache ist eine Datei und sonst nichts;
Sprachauswahl, Einsammler, Handbuch, Abbildungen und Prüfung lesen das
Verzeichnis über `available_languages()`, nicht eine Liste im Code. Wer hier
zwei Sprachen fest hinschreibt, hat die siebte schon vergessen — und die
Prüfung prüft jede gefundene Datei, nicht die englische.

### 4.2 Begriffe

| Deutsch (Doku) | Code | Bedeutung |
|---|---|---|
| Operation, Op | `Operation` / `op` | eine Änderung im Stack |
| Transaktion | `Transaction` | Gruppe von Ops, gemeinsam rücknehmbar |
| Szene | `Scene` | alle Objekte plus Parameter, Passungen, Stack |
| Objekt | `SceneObject` | ein Körper in der Szene |
| Baustein | `Part` | parametrisches Fertigteil aus der Bibliothek |
| Feature | `Feature` | erkannte Bohrung, Fläche, Kante |
| Provenienz | `provenance` | Herkunft eines Features oder einer Op |
| Steckbrief | `digest` | Textbeschreibung der Szene für den Agenten |
| Prüfbericht | `report` | Befunde aus Eingangsstufe, Ops und Prüfungen |
| Rückfallkette | `solver chain` | Stufen bei gescheiterter Boolescher Op |
| Passung | `Fit` | benannte Beziehung zweier Features |
| Profil | `Profile` | Drucker- oder Materialeinstellungen |
| Regelsammlung | `rules` | Druckregeln für Agent und Prüfungen |
| Bausteindatei | `part_file` | lokaler, offline geprüfter Import und Export eines Bausteinrezepts |
| Lizenz | `licence` | Nutzungsrechte an einer Bausteindatei; das Dataclass-Feld und der Dateischlüssel heißen `license`, der Parametername bleibt wegen der Builtin-Schattung `licence` |

Diese Zuordnung ist verbindlich. Ein neuer Begriff kommt zuerst in diese
Tabelle, dann in den Code.

---

## 5. Verteilungsmodell

| | |
|---|---|
| **Produkt** | Desktop-Anwendung, als Download veröffentlicht |
| **Online** | Website mit Doku und Downloads |
| **Vorgesehener optionaler Ausbau** | gehosteter Generierungs-Backend für Nutzer ohne geeignete lokale GPU, über dieselbe Grenze aus §27 |
| **Ausdrücklich nicht** | Web-Anwendung im Browser, Mehrbenutzerbetrieb, Cloud-Ablage |

Wichtigster Nebeneffekt: **Auf dem Server läuft niemals Code, den ein LLM
erzeugt hat.** Er läuft auch lokal nicht (§32); der gehostete Backend nimmt
nur Text oder Bild und gibt ein Mesh zurück.

---

## 6. Die drei Säulen

| | **A — Konstruieren** | **B — Generieren** | **C — Bearbeiten** |
|---|---|---|---|
| Eingabe | Beschreibung + Maße | Text oder Bild | STL/3MF/OBJ + Anweisung |
| Motor | LLM → Op-Liste aus Bausteinen, Primitiven und Skizzen | ComfyUI lokal *oder* gehostet | Feature-Erkennung + Boolesche Ops |
| Ergebnis | parametrisch, maßhaltig | organisch, optional texturiert | bearbeiteter Körper als Mesh oder B-Rep |
| Ausführungsort | immer lokal | lokal oder Backend | immer lokal |

Säule A hat genau **eine** Ausgabeform: die Op-Liste aus Bausteinen,
Grundformen und Skizzenoperationen. Sie bleibt im Kern, ist schemageprüft, im Stack sichtbar,
rücknehmbar, erzeugt Provenienz-Features und kann Projektparameter benutzen.

Eine Rückfallebene daneben gibt es nicht, und sie fehlt auch nicht: Was sich
nicht als Baustein fassen lässt, entsteht als Skizze mit Extrudieren, Drehen,
Sweep oder Loft gegen den exakten Kern (§30.1). Auch eine Freiform bleibt
damit parametrisch, maßhaltig und rücknehmbar.

---

## 7. Schichtenaufbau

```
╔══ ui ══════════════════════════════════════════════════════╗
║  PySide6 — Viewport │ Objektbaum │ Parameter │ Verlauf │    ║
║       Auswahl │ Chat / Prüfbericht │ Statusleiste          ║
╚══════════════════════┬═════════════════════════════════════╝
                       │  einzige erlaubte Richtung ↓
╔══ core ═══════════════════════════════════════════════════════╗
║  Operationsregister (§10) — Quelle für alle Oberflächen       ║
║  Szenenmodell — Objekte, Parameter, Passungen, Op-Stapel,     ║
║  Auswertung, Undo/Redo, Caching, Projektdatei                 ║
║      ┌──────────────┬──────────────────┬──────────────────┐   ║
║  ┌───▼─────────┐ ┌──▼──────────────┐ ┌─▼───────────────┐      ║
║  │Geometriekern│ │ Wahrnehmung     │ │ Wissensbasis    │      ║
║  │manifold3d   │ │ Features,       │ │ Bausteine (Py), │      ║
║  │trimesh      │ │ Steckbrief,     │ │ Normteile,      │      ║
║  │(B-Rep §30)  │ │ Analysekarten   │ │ Profile, Regeln │      ║
║  └─────────────┘ └──┬──────────────┘ └─────────────────┘      ║
║                     │ speist Viewport UND Agent               ║
║              ┌──────▼─────────────────────────────────────┐   ║
║              │ Agentenschicht — LLM, Werkzeuge, Kontext   │   ║
║              └──────┬─────────────────────────────────────┘   ║
╚═════════════════════┼═════════════════════════════════════════╝
              ┌───────▼────────────────────┐
              │ Backends (austauschbar §27)│
              │ LLM: Cloud │ lokal         │
              │ Mesh: ComfyUI │ gehostet   │
              └────────────────────────────┘
```

---

## 8. Paketstruktur und Kernabgrenzung

Der Bauplan legt die **Grenzen** fest, nicht das Inhaltsverzeichnis: welche
Schicht welche benutzen darf, und wo etwas hingehört, das neu ist. Die
gepflegte Karte mit jedem Modul steht in `CLAUDE.md`. Zwei Karten wären zwei
Quellen, und die zweite ist immer die veraltete (Leitprinzip 3) — diese hier
war es: Sie kannte `sketch/` und `brep/` nicht, obwohl §30.1 beide verlangt,
und legte `tests/` unter `app/`, wo es nie lag.

```
app/
  core/            kein Qt, keine Dialoge — nach außen nur über OpContext
    registry/      Operationsregister, Schemata, Erzeugung der Oberflächen
    scene/         Szene, Parameter, Passungen, Op-Stapel, Auswertung,
                   Projektdatei, Migrationen
    geom/          Operationen, Geometriekerne, Rückfallketten
    sketch/        Skizzen mit Zwangsbedingungen (§30.1) — Solver, Profile
    brep/          zweiter Konstruktionskern (§30), optional
    slice/         Schichtanalyse (§22)
    ingest/        Eingangs-Normalisierung (§17.1)
    perceive/      Feature-Erkennung, Analysekarten, Steckbrief
    knowledge/     Bausteine, Normteile, Profile, Regelsammlung
    agent/         LLM-Anbindung, Werkzeuge, Kontextverwaltung
    backends/      LLM- und Mesh-Backends hinter einer Schnittstelle
    export/        Schreiben, Slicer-Übergabe, Namensschema
    activation/    Kaufcode, Geräteidentität, signiertes Zertifikat,
                   Demo- und optionale Testfrist
    errors.py      Ausnahmehierarchie (§33)
    types.py       Kernverträge (§9)
  ui/              PySide6 — darf core benutzen, nie umgekehrt
  cli/             Kommandozeilen-Einstieg auf core
  i18n/            deutsche Quelle plus je Sprache ein Katalog (§4.1)
tests/
  data/            Referenzkorpus (§34)
```

**Was weder Geometrie noch Oberfläche ist, liegt trotzdem im Kern**, wenn es
ohne Fenster laufen muss: Handbuch, Abbildungskatalog, Zeichnungen,
Fehlerbericht, Rückmeldung, Aktualisierung. Der Grund ist derselbe wie bei
allem anderen dort — ohne Qt aufrufbar heißt prüfbar, und ein Handbuch, das
nur entsteht, wenn ein Fenster offen ist, entsteht in keinem Testlauf.

**Die Regel:** `core` importiert niemals aus `ui`. Ein Test importiert `core`
ohne installiertes Qt; bricht er, ist die Trennung verletzt.

**Betreiberwerkzeuge reisen nicht mit dem Produkt.** Die private
Support-Verwaltung liegt unter `tools/` und spricht mit einem eng begrenzten
JSON-Endpunkt des Aktivierungsdienstes; sie ist weder ein versteckter Modus der
Kundenanwendung noch eine Web-Anwendung. Zugang gibt ein zufälliger
256-Bit-Token, der wie der Aktivierungsstartwert außerhalb von Repository und
Webroot liegt. Der Server kennt weiterhin nur den Digest einer Lizenz. Die
Zuordnung zu Bestellkennung und Käuferkennung entsteht ausschließlich im
privaten, offline gesicherten Schlüsselarchiv des Betreibers. Ein anonymer
Vorratsschlüssel bekommt dort seine MoR-Transaktionskennung; erst der Blick ins
Dashboard des Zahlungsanbieters löst sie zu einem Käufer auf.

Vier Serverhandlungen gehören zum Supportvertrag: künftige Aktivierungen
sperren oder wieder freigeben, den belegten Geräteplatz für einen Wechsel
freigeben und das Tageslimit nach einem geklärten Fehlerfall zurücksetzen. Jede
Änderung trägt einen festen Anlass und einen Audit-Eintrag ohne Freitext oder
Kundendaten. Keine davon schaltet eine bereits ausgestellte Offline-
Freischaltung aus der Ferne ab — das wäre nur mit einer regelmäßigen
Lizenzabfrage möglich und widerspräche Leitprinzip 8.

---

## 9. Kernverträge

Die Signaturen, an denen sich alle Module ausrichten. Die Datenverträge
stehen in `app/core/types.py`, `solve_sketch` in `app/core/sketch/solver.py`.
Der Auszug zeigt Felder und Vorgaben; Importe und Methoden sind ausgelassen.
Vertragsänderungen werden vor ihrer Nutzung in abhängigen Modulen festgelegt.

```python
@dataclass(frozen=True, slots=True)
class Feature:
    id: FeatureId
    kind: FeatureKind
    provenance: Provenance
    params: Mapping[str, Any]
    face_indices: tuple[int, ...] = ()
    recognised: bool = True
    created_by: OpId | None = None


@dataclass(slots=True)
class SceneObject:
    id: ObjectId
    name: TranslatableText | str
    mesh: Mesh
    kind: ObjectKind = 'mesh'
    features: dict[FeatureId, Feature] = field(default_factory=dict)
    material_slots: list[MaterialSlot] = field(default_factory=list)
    material: str | None = None
    plate: int = 0
    created_by: OpId = 0
    visible: bool = True
    reserved_feature_ids: tuple[FeatureId, ...] = ()


@dataclass(slots=True)
class Scene:
    objects: dict[ObjectId, SceneObject] = field(default_factory=dict)
    parameters: dict[ParameterName, Parameter] = field(default_factory=dict)
    fits: list[Fit] = field(default_factory=list)
    profile: Profile | None = None
    report: Report = field(default_factory=Report)


@dataclass(slots=True)
class OpContext:
    scene: Scene
    inputs: list[SceneObject]
    params: BaseParams
    profile: Profile
    quality: Quality
    seed: int | None
    progress: ProgressFn
    ask: AskFn
    cancelled: CancelToken
    sources: SourceAccess | None = None


@dataclass(slots=True)
class OpResult:
    outputs: list[SceneObject]
    solver: SolverInfo | None = None
    findings: list[Finding] = field(default_factory=list)
    answered: dict[str, Any] = field(default_factory=dict)
    transform: Transform | None = None


@dataclass(frozen=True, slots=True)
class LayerInfo:
    z: float
    contours: tuple[Polygon, ...]
    area: float
    overhang_area: float
    islands: tuple[Polygon, ...]
    min_width: float
    overhangs: tuple[Polygon, ...] = ()
    bridge_width: float = 0.0


@dataclass(frozen=True, slots=True)
class SliceResult:
    layers: tuple[LayerInfo, ...]
    support_volume: float
    first_layer_area: float
    source: MetricSource = 'internal'


@dataclass(frozen=True, slots=True)
class SketchElement:
    kind: SketchElementKind
    points: tuple[Point2, ...]
    construction: bool = False


@dataclass(frozen=True, slots=True)
class SketchConstraint:
    kind: SketchConstraintKind
    targets: tuple[int, ...]
    value: str = ''


@dataclass(frozen=True, slots=True)
class Sketch:
    plane: str
    elements: tuple[SketchElement, ...]
    constraints: tuple[SketchConstraint, ...] = ()


OpFn = Callable[[OpContext], OpResult]


def solve_sketch(
    sketch: Sketch, params: Mapping[str, float] | None = None
) -> SolvedSketch:
    """Löst deterministisch; Freiheitsgrade und kollidierende Bedingungen
    werden als Befund beziehungsweise handlungsfähiger Fehler gemeldet."""
```

Die Typaliase und ihre Bedeutung gehören zu diesem Vertrag:

- `FeatureKind`: `hole`, `face`, `edge_loop`, `pin`, `cone`, `sphere`,
  `torus`, `thread`, `fillet`. `provenance` unterscheidet `detected` und
  `generated`; `recognised=False` erhält eine Kennung auch dann, wenn ihr
  Merkmal derzeit nicht sicher erkannt wird (§21.3).
- `ObjectKind`: `mesh` oder `brep`; `Quality`: `draft` oder `fine`.
  `MetricSource`: `internal` oder `gcode` — nie vermischen (§22.5).
- `SketchElementKind`: `point`, `line`, `arc`, `circle`, `spline`.
  `construction` kennzeichnet Hilfsgeometrie.
- `SketchConstraintKind`: `distance`, `radius`, `diameter`, `coincident`,
  `horizontal`, `vertical`, `parallel`, `perpendicular`, `tangent`,
  `symmetric`, `fixed`, `reference`. `targets` referenziert die flache
  Punktliste, `value` trägt einen Maßausdruck aus §13. Die Skizzenebene ist
  `plane:xy`, `plane:xz`, `plane:yz` oder
  `feature:<object_id>:<feature_id>`. Die Kurzform `feature:<id>` bleibt
  für ältere Skizzendaten lesbar.
- `progress(fraction, text)` meldet den Fortschritt;
  `ask(question, choices)` liefert die gewählte Antwort. `sources` vermittelt
  den Zugriff auf Projektquellen ohne globale Ablage.
- `OpResult.answered` führt beantwortete Parameter zurück zum Aufrufer
  (§15.7); `transform` beschreibt eine angewandte Transformation für die
  anschließende Merkmalszuordnung. `solver` hält die Rückfallstufe fest.
- `SceneObject.material` und `plate` ordnen Material und Druckplatte zu;
  `reserved_feature_ids` verhindert die Wiedervergabe früherer Merkmalsnamen.
  Namen dürfen übersetzbare Texte tragen. `Scene.profile=None` beschreibt
  eine noch nicht zugeordnete Szene; eine rechnende Op erhält ein aufgelöstes
  `OpContext.profile`.

**Vier Regeln, die aus diesen Verträgen folgen:**

1. **`OpContext.scene` ist nur lesend.** Eine Op erzeugt neue Objekte, sie
   ändert keine bestehenden. Die Auswertung schützt den Szenenzustand durch
   getrennte Kontextdaten; veränderliche Dataclasses allein erzwingen diese
   Regel nicht. Eingänge und ihre Netze bleiben ebenfalls nur lesend.
2. **Jede Op meldet `findings` statt zu protokollieren.** Der Kern entscheidet,
   was daraus im Bericht und im Steckbrief erscheint.
3. **`progress`, `ask` und `cancelled` sind Teil des Vertrags**, nicht Zugriffe
   auf globale Objekte — das ist die technische Absicherung der Kerntrennung.
4. **`quality` reicht durch.** Jede Op muss beide Stufen beherrschen, notfalls
   indem sie sie gleich behandelt.

Weitere feste Verträge: `PartFn` für Bausteine (§24.1), `MeshBackend` und
`LLMBackend` für Backends (§27), `Migration` für Formatwechsel (§16.2).

---

## 10. Operationsregister

Eine Operation wird genau einmal deklariert; alles Weitere wird erzeugt.

```python
@register_op(
    name="resize_hole",
    title=_("Bohrung ändern"),
    category="holes",
    params=ResizeHoleParams,
    reversible=True,
    consumes=1,
    produces=1,
    applies_to=["hole"],  # steuert das Kontextmenü am Feature
    touches_features=True,
    deterministic=False,  # Boolesche Rückfallkette kann Jitter benötigen
    doc=_("Ändert den Durchmesser einer erkannten Bohrung."),
)
def resize_hole(ctx: OpContext) -> OpResult: ...
```

| Ausgabe | Woraus |
|---|---|
| Menüeintrag und Dialog | `title`, `category`, Parameterschema |
| Kontextmenü am Feature | `applies_to` |
| Befehlspalette und Kürzel | `title`, `doc`, `shortcut` |
| Kommandozeilen-Befehl | `name`, Parameterschema |
| Tool-Schema für den Agenten | `name`, `doc`, JSON-Schema aus `params` |
| Doku-Abschnitt | alles zusammen |
| Prüfungen im Stack | `consumes`/`produces`, `reversible`, `deterministic` |

**Konsistenztest**: Jede Op ist über das gemeinsame Register erschlossen
und besitzt Schema, Geometrietest und übersetzte Texte. Die jeweiligen
Ausgaben berücksichtigen Auswahl und unterstützte Körperart; zusammengelegte
Menüeinträge beziehen sich auf denselben Vertrag. Kein Kürzel ist doppelt;
nicht-deterministische Ops führen einen Startwert; `applies_to` nennt nur
bekannte Feature-Arten.

**Stelligkeit und Identität werden deklariert.** `consumes=VARIABLE` erlaubt
variable Eingänge; `minimum_inputs` legt deren Untergrenze fest. Alle Aufrufer
lesen diese über `needed_inputs()`. `whole_scene` erklärt den Zugriff auf
alle Objekte, `requires_kind` eine benötigte Körperart. Bei variablen
Ausgängen leitet `produces_from` deren Anzahl aus einem Parameter ab.
Ohne dieses Feld erhält `produces=VARIABLE` vorhandene Eingänge; ein
eingangsloser Erzeuger wie `load` verwendet die vorab deklarierte
Ausgangszahl. Eine leere Gesamtszenen-Operation erzeugt keine Objekte.
`keeps_inputs` bestimmt bei fester Ausgangszahl, welche ersten Ausgänge die
Kennungen ihrer Eingänge fortführen. Keine Oberfläche errät diese Regeln
aus dem Namen der Operation.

**Parameterschema** trägt Grenzen, Einheiten, Vorgabewerte und die Zuordnung
zu Vorder- oder Rückseite des Dialogs (§2.4) — dieselbe Definition validiert
Dialog, Kommandozeile und Agentenaufruf.

---

## 11. Zahlen, Einheiten, Toleranzen, Determinismus

### 11.1 Einheiten
Der Kern rechnet **ausschließlich in Millimetern** und in doppelter
Genauigkeit. Eine andere Anzeigeeinheit ist reine Oberflächensache und
erreicht den Kern nie. Umrechnungen passieren genau zweimal: beim Import
(§17.1) und in der Anzeige.

### 11.2 Drei benannte Toleranzen

| Name | Größenordnung | Wofür |
|---|---|---|
| `EPS_GEOM` | 1e-6 mm | koinzidente Punkte, Nullflächen, Verschweißen |
| `EPS_DISPLAY` | 0,01 mm | Rundung in Bemaßung, Steckbrief, Berichten |
| `match_tolerance(diagonal_mm)` | max. aus 0,01 mm und 0,5 % der Modelldiagonale | allgemeine größenabhängige Vergleiche |

Die Konstanten stehen in `app/core/units.py`: `EPS_MATCH_RELATIVE` und
`EPS_MATCH_MINIMUM` bestimmen `match_tolerance()`. Die Merkmalszuordnung aus
§21.3 nutzt eigene, geprüfte Kosten und Annahmeschwellen in
`app/core/perceive/matching.py`; diese Funktion steuert sie nicht.

Numerische Genauigkeit, Erkennungsunsicherheit und Fertigungsspiel sind
verschiedene Größen. Fertigungstoleranzen kommen aus dem Materialprofil,
die Messunsicherheit der Passungsprüfung aus §14. Gerundet wird nur in der
Anzeige. Fließkommazahlen werden nie mit `==` verglichen.

### 11.3 Determinismus
Randomisierte Verfahren umfassen die Jitter-Rückfallstufe (§17.2),
Farbquantisierung (§20) und konvexe Zerlegung beim Auto Split. Jede betroffene
Operation bekommt
einen **Startwert, der in der Op gespeichert wird**, ist im Register als
`deterministic=False` gekennzeichnet und liefert bei gleichem Startwert
dasselbe Ergebnis. Ohne diese Regel ist Leitprinzip 4 nicht haltbar und ein
Fehlerbericht reproduziert nichts.

Die Orientierungssuche soll ihre Kandidaten gemäß §28.2 aus der
konvexen Hülle gewinnen. Solange ein Rechenweg zusätzlich Zufallsrichtungen
abtastet, gilt auch dort der gespeicherte Startwert; die Anforderung aus
§28.2 ist dadurch nicht erledigt.

**Nebenläufigkeit muss reproduzierbar bleiben.** Die Schichtanalyse kann
unabhängige Schichten mit den vorgesehenen Workern berechnen (§31). Das
bleibt reproduzierbar, solange jeder Thread eine Schicht für sich rechnet und
die Summen in feststehender Reihenfolge gebildet werden. Eine Reduktion, die in
der Reihenfolge der Fertigstellung addiert, ist es nicht — Fließkommaaddition
ist nicht assoziativ, und der Unterschied steht dann in der letzten Stelle
eines Volumens, das ein Bericht ausweist. Wer eine Rechnung parallelisiert,
prüft sie mit demselben Test, der zweimalige Auswertung vergleicht (§15.1).

---

## 12. Szenenmodell

Das folgende Beispiel zeigt Import, Reparatur und Teilen im Dateiformat 20.
Versionswerte kennzeichnen den Beispielstand und werden beim Speichern aus
der tatsächlichen Installation geschrieben. `…` ersetzt hier ausschließlich
Quellen-/Herkunftsdaten; insbesondere muss eine echte Datei einen gültigen
SHA-256-Wert tragen. Der Auszug ist kein vollständiger Projektcontainer.

```json
{
  "format_version": 20,
  "app_version": "0.3.5",
  "libs": {"manifold3d": "3.5.2", "trimesh": "5.1.0"},
  "parts_version": "12",
  "scene": {"printer": "centauri-carbon-2", "material": "petg"},
  "parameters": {
    "width": {"value": 84.0, "unit": "mm", "min": 40, "max": 200,
               "title": "Breite", "title_translatable": true},
    "height": {"value": 22.0, "unit": "mm", "min": 10,
              "title": "Höhe", "title_translatable": true}
  },
  "sources": {
    "src_1": {"type": "import", "path": "sources/halterung.stl",
              "sha256": "…", "embedded": true,
              "ingest": {"unit": "mm", "scale": 1.0, "welded": true,
                         "removed_triangles": 0, "components": 1},
              "origin": {"url": "…", "license": "CC BY-NC 4.0",
                         "author": "…", "retrieved": "2026-07-20"}}
  },
  "fits": [
    {"name": "stift_1", "a": "obj_2:pin_1", "b": "obj_3:bore_1",
     "type": "clearance", "tolerance": "auto:petg"}
  ],
  "transactions": [
    {"id": "t1", "title": "Import und Reparatur",
     "title_translatable": true, "origin": {"by": "user"},
     "ops": [1, 2]},
    {"id": "t2", "title": "Teilen und verstiften",
     "title_translatable": true,
     "origin": {"by": "agent", "model": "…", "prompt_version": "3",
                "rules_version": "7", "temperature": 0.2},
     "ops": [3, 4]}
  ],
  "ops": [
    {"id": 1, "op": "load",        "in": [],                "out": ["obj_1"],
     "params": {"source": "src_1", "unit": "mm", "name": "Halterung"},
     "translatable": ["name"]},
    {"id": 2, "op": "repair",      "in": ["obj_1"],         "out": ["obj_1"],
     "params": {"fill_holes": true}},
    {"id": 3, "op": "split_pinned", "in": ["obj_1"],
     "out": ["obj_2", "obj_3"],
     "params": {"axis": "z", "position": "=@height/2", "pins": 3,
                "diameter": 4.0, "play": 0.0},
     "solver": {"strategy": "direct"}, "seed": 20260727},
    {"id": 4, "op": "arrange_bed", "in": ["obj_2", "obj_3"],
     "out": ["obj_2", "obj_3"],
     "params": {"spacing": 5.0}}
  ],
  "chat": [],
  "numbering": {"transaction": 2, "op": 4, "object": 3},
  "print_settings": null
}
```

Die Abhängigkeiten über `in`/`out` bilden Teilen (1 → 2) und Vereinigen
(2 → 1) ab; der Verlauf bleibt ein linearer Stapel ohne alternative Äste.
`auto:petg` bindet die Passungsprüfung an ein Materialprofil; bei der Op
`split_pinned` bedeutet der numerische Vorgabewert `play: 0.0`, dass das
Spiel aus dem Profil abgeleitet wird. `=@height/2` verweist auf einen
Projektparameter (§13), `solver` und `seed` halten Rückfallstufe und
Startwert fest (§11.3, §17.2).

Zusätzlich zum gezeigten Grundfall gehören zum Format:

- `matches` je Operation speichert geometrische Zuordnungsantworten (§15.7).
  Merkmalsreferenzen bestehen aus Objektkennung und lokalem Merkmalsnamen;
  eine erfundene Op-Vorsilbe gehört nicht hinein (§21.2).
- Transaktionen können `changes` mit Vorher-/Nachher-Zuständen tragen.
  Parameteränderung und Löschen bleiben dadurch rücknehmbar (§15.4–15.5).
- `numbering` hält die höchsten vergebenen Transaktions-, Op- und
  Objektkennungen auch über Undo/Redo und Speichern hinweg fest. Frühere
  Kennungen dürfen nicht für andere Inhalte wiederverwendet werden.
- `print_settings` trägt bei zugewiesenen Druckeinstellungen die portablen
  Drucker-, Filament-, Slicer- und Kalibrierdaten im Projekt. `null` bedeutet
  keine gespeicherte Zuweisung. Ein unbekanntes Material bleibt unbekannt;
  beim Öffnen wird daraus nicht stillschweigend PLA.
- Umfangreiche gesammelte Parameterwerte werden im Container unter
  `sources/gathered/` abgelegt und im gespeicherten Parameter über `source:`
  referenziert (§16.1). Im Arbeitsdokument steht der aufgelöste Wert.

Die vollständige Serialisierung steht in `app/core/scene/serialise.py`, die
Schema- und Containerprüfung in `app/core/scene/project.py`, die
Versionskette in `app/core/scene/migrations.py`.

---


## 13. Projektparameter

Benannte Größen auf Szenenebene, auf die Ops verweisen. Damit wird aus jedem
Projekt eine Vorlage: „dieselbe Halterung, andere Maße" ist ein Zahlendialog
statt einer neuen Sitzung.

- **Verweis** `"@width"` oder Ausdruck `"=@width/2 - @wall"`
- **Ausdrücke sind eingeschränkt**: Zahlen, Parameter, `+ - * /`, Klammern,
  `min`, `max`, `round`, `abs`. Eigener Auswerter über eigener Grammatik —
  **kein `eval`**, auch nicht abgesichert (§32).
- **Zyklen** werden beim Setzen erkannt und abgelehnt.
- **Parameterleiste** links: Name, Wert, Einheit, Schieberegler bei
  begrenztem Bereich. Änderung rechnet nur die abhängigen Zweige neu (§15).
- **Der Agent legt Parameter an, statt Zahlen zu streuen** — verpflichtend,
  sobald ein Wert zweimal vorkommt oder erkennbar eine Hauptabmessung ist. Die
  Agenten-Suite misst es.
- **Vorlagen** ergeben sich fast von selbst: Ein Projekt ohne Quellen, nur mit
  Parametern und Bausteinen, ist eine Vorlage (§41).

---

## 14. Passungsbeziehungen

Objekte sind sonst unabhängig, und ein Fehler fällt erst beim Zusammenbau auf.

```json
{"name": "stift_1", "a": "obj_2:pin_1", "b": "obj_3:bore_1",
 "type": "clearance", "tolerance": "auto:petg"}
```

- **Arten**: `clearance` (Spiel), `press` (Presspassung), `thread` (Gewinde),
  `flush` (bündig, für Flächen)
- **Prüfung bei jeder Auswertung**: Passen Merkmalsarten und Maße
  zur geforderten Verbindung? `clearance` und `press` prüfen das Spiel;
  `thread` außerdem Gewindeart und Steigung; `flush` Flächennormalen und
  Abstand. Verletzungen und fehlende Referenzen erscheinen im Prüfbericht,
  Steckbrief und als Analysekarte (§18.4), nie stillschweigend.
- **Fertigungsspiel und Messunsicherheit getrennt halten.** `auto:<material>`
  liest das gewünschte Spiel aus dem benannten Profil; `auto:` folgt den
  tatsächlich zugeordneten Materialien. Die Prüfung tessellierter oder
  erkannter Merkmale verwendet `FIT_TOLERANCE` aus
  `app/core/scene/fits.py` (derzeit 0,05 mm), statt Scheingenauigkeit von
  `EPS_GEOM` zu versprechen. Dieser Prüfbereich ersetzt nicht das
  Fertigungsspiel.
- **Bedingte Passungen** tragen `when_positive: [op_id, parameter]`.
  Sie sind bei einem gültigen Wert kleiner oder gleich null inaktiv, bleiben
  aber im Dokument erhalten, etwa wenn ein Deckel seinen Stift vorübergehend
  ausschaltet. Fehlende oder ungültige Referenzen sind Fehler und keine
  Erlaubnis, eine Passung still auszublenden.
- **Auto Split legt die Paare automatisch an** — dort entstehen sie ohnehin.
- **Der Agent kann Paare anlegen**; die Suite prüft, ob er es tut.

---

## 15. Auswertung und Neuberechnung

### 15.1 Auswertung als reine Funktion
`Stack + Quellen + Parameter + Profile + Startwerte → Szene`. Kein versteckter
Zustand, keine Seiteneffekte. Zweimal ausgewertet ergibt zweimal dasselbe.

### 15.2 Geänderte Objektzahl
Die Auswertung vergleicht die Ergebniszahl mit der gespeicherten Liste `out`.
Gleiche Anzahl → Bindung über deren Position. Abweichende Anzahl → Halt an
der liefernden Op, bevor ihre Ausgaben in die Szene übernommen werden. Das
gilt für zusätzliche und fehlende Objekte, auch ohne nachfolgende Operation.
Bestehende Bindungen werden nicht automatisch umnummeriert.

Eine bewusste Parameteränderung darf die erwartete Ausgangsliste erneuern,
wenn keine spätere Operation davon abhängt. Andernfalls muss der Nutzer die
abhängigen Schritte gezielt entfernen oder neu zuordnen. Kein automatisches
Nachrücken.

### 15.3 Angehaltene Kette
Der Viewport zeigt **den letzten vollständig gerechneten Zustand**, nie ein
leeres Fenster, dazu einen Hinweis in der Statusleiste und die betroffenen Ops
im Verlauf markiert. Alles davor bleibt bedienbar.

### 15.4 Keine Verzweigungen
Eine Änderung nach einem Undo verwirft den zurückgenommenen Verlauf; bei
mehr als einer zurückgenommenen Transaktion wird vorher nachgefragt.
Alternative Stack-Verzweigungen
gehören nicht zum Produktumfang (§41).

Ein gewählter Schritt darf unabhängig davon als **neue Transaktion** aus der
Mitte gelöscht werden. Spätere Ops, deren frische Eingabe damit verschwindet,
gehen in derselben Transaktion mit; unabhängige Zweige bleiben stehen. Behält
die Kette dieselbe Objektkennung — etwa vor und nach einer Bohrung —, arbeiten
spätere Schritte auf dem Zustand davor weiter. Eine Nachfrage nennt vorab,
ob abhängige Schritte betroffen sind, und dass Strg+Z alles gemeinsam
wiederherstellt. Die ursprüngliche Zeile bleibt durchgestrichen als Geschichte
sichtbar. Das ist keine Verzweigung: Es gibt weiterhin genau einen aktuellen
Stack.

### 15.5 Transaktionen
Mehrere Ops können als benannte Gruppe eingetragen werden. **Undo nimmt die
ganze Gruppe.** Jeder Agentenvorschlag ist genau eine Transaktion — sonst muss
der Nutzer achtmal rückgängig machen, was der Agent einmal vorgeschlagen hat.
Einzelne manuelle Operationen bilden je eine Transaktion; ein zusammengehöriger
Bedienablauf kann mehrere Ops gemeinsam anwenden. Die Transaktion trägt Titel und
Herkunft (§26.4) und ist die Einheit, auf die sich Verlauf, Differenzansicht
und Chatverlauf beziehen.

**Eine Ausnahme, und sie ist eng:** Aufeinanderfolgende gleichartige Züge —
dieselbe Operation auf denselben Eingängen mit demselben Anker — verschmelzen
zu einem Schritt; das Bündel endet mit jeder anderen Handlung. Der Grund ist
der Kunde, der ein Teil an seinen Platz schiebt: Er zieht, sieht nach, zieht
nach, und das ist eine Absicht und nicht drei. Ein Strg+Z nahm davon bisher ein
Drittel zurück.

**Gebündelt wird nur, wo eine Kumulationsregel steht** — das ist opt-in je
Operation und nicht die Voreinstellung. Zwei Verschiebungen sind eine
Vektorsumme, zwei Drehungen um dieselbe Achse eine Winkelsumme; um
verschiedene Achsen gibt es keine gemeinsame Drehung, und der Versuch wäre ein
stiller Geometriefehler. Skalieren bündelt vorerst nicht: Multiplikativ wäre es
rechenbar, aber der Kundenfall ist das Nachschieben, und was fehlt, kann
dazukommen — umgekehrt wäre es ein Rückbau.

### 15.6 Abbruch und Nebenläufigkeit
Eine laufende Berechnung ist jederzeit abbrechbar; der Stack bleibt auf dem
letzten vollständig gerechneten Stand — **keine halb angewandten Ops**. **Ein
Rechenlauf je Dokument**; weitere Anforderungen ersetzen die wartende
(Entprellung). Der Cache wird erst nach vollständigem Durchlauf geschrieben.

### 15.7 Antworten auf Rückfragen werden im Dokument gespeichert
Regel 21 verlangt anzuhalten und zu fragen, statt zu raten — über `ctx.ask`
(§9). Eine Antwort darf kein ungeschriebener Eingang der Auswertung werden:
Sie reist mit der Projektdatei und muss nach Speichern, Öffnen und ohne Cache
dieselbe Entscheidung bewirken (§15.1).

**Zwei Arten von Antworten haben unterschiedliche Speicherorte.**

- Was eine Operation selbst erfragt, etwa die Einheit in `load` (§17.1),
  gehört in ihre Parameter. Die Op meldet den Wert über `OpResult.answered`;
  die Auswertung sammelt ihn in `EvaluationResult.answers`. Der Aufrufer schreibt
  ihn über `History.record_answers()` zurück. Der geänderte Parameter-Hash
  bewirkt einmal die Neuberechnung des abhängigen Zweigs.
- Was die Merkmalszuordnung entscheidet (§21.3), steht im Feld
  `Operation.matches`. Es ist kein erfundener Schlüssel im Op-Parameterschema.
  Die Auswertung liefert die Zuordnungen in `EvaluationResult.matches`, der
  Aufrufer schreibt sie über `History.record_matches()` zurück.

Die reine Auswertung ändert das Dokument nicht selbst. Beide Rückschreibwege
ergänzen die fragende Handlung und erhalten **keine eigene Transaktion**;
das Dokument gilt danach als geändert und muss gespeichert werden.
Eine vom Nutzer nachträglich veranlasste Parameteränderung über
`History.change_params()` ist dagegen eine eigene, rücknehmbare Änderung.

**Eine Merkmalskennung allein ist kein zuverlässiger Speicherwert.**
`matches` hält den geometrischen Abdruck des gewählten Merkmals fest, unter
anderem Art, Lage, Achse und Maße. Nur wenn ein Kandidat hinreichend passt und
einen ausreichenden Abstand zum zweiten hat, darf die Zuordnung ohne Rückfrage
übernommen werden. Bei verschobener Geometrie oder erneuter Mehrdeutigkeit
wird wieder gefragt. Geänderte Nummerierung darf nie still ein anderes Loch
auswählen.

**Der Cache darf keine Entscheidung ersetzen.** Ein Ergebnis, bei dessen
Berechnung `ctx.ask` benutzt wurde, bleibt zunächst im Sitzungsspeicher;
es wird nicht in den Plattencache geschrieben. Das gilt für Fragen der Op
und der anschließenden Merkmalszuordnung. Erst nachdem die Antwort im
Dokument steht und ein weiterer Lauf ohne neue Rückfrage auskommt, ist dessen
Ergebnis dauerhaft cachefähig. Das Löschen des Caches darf weder eine
gespeicherte Entscheidung verlieren noch eine neue Mehrdeutigkeit verdecken.

**Abnahme:** Echte mehrdeutige Geometrie wählen, einmal beantworten,
speichern und in einer neuen Sitzung jeweils mit und ohne warmen Cache
öffnen. Beide Wege müssen dieselbe Zuordnung ohne wiederholte Frage liefern.
Danach die Geometrie so ändern, dass der Abdruck nicht mehr eindeutig passt:
Die Rückfrage muss wieder erscheinen. Vorhandene Rückschreib- und
Formatmechanismen ersetzen diese Endabnahme nicht; ihr Rest steht bei
RM-024 in `ROADMAP.md`.

---


## 16. Projektdatei

### 16.1 Container
```
projekt.p3d           (ZIP)
  project.json        # Stack, Parameter, Passungen, Transaktionen
  sources/            # eingebettete Quelldaten
    gathered/         # umfangreiche gesammelte Parameterwerte
  report.json         # letzter Prüfbericht
  thumb.png           # Vorschaubild für Dateidialoge
```
Quellen wahlweise eingebettet oder verlinkt; **für die Weitergabe ist
Einbetten die Vorgabe**. Prüfsummen in beiden Fällen, beim Laden verifiziert.
Verlinkte Quellen verwenden relative Pfade. Gesammelte Werte werden beim
Laden aufgelöst; ein fehlender oder unzulässiger Verweis wird als Fehler mit
Handlungsvorschlag behandelt. Ausführbarer Quelltext reist nie mit (§32);
Bausteinrezepte dürfen registrierte Operationen und Daten enthalten (§24.5).

### 16.2 Version und Reproduzierbarkeit
- **`format_version`**: gleich → laden, älter → Migrationskette, neuer →
  freundlich ablehnen statt halb zu laden
- **Migrationen** als eigene Funktionen mit Test und eingecheckter
  Beispieldatei je Altversion
- **`libs`** hält fest, womit gerechnet wurde; Abweichung ergibt einen Hinweis,
  keinen Abbruch
- **`parts_version`** hält den Stand der Bausteinbibliothek fest (§24.4).
  Beim Öffnen mit neuerem Stand nennt der Hinweis **welche benutzten Bausteine
  sich geändert haben**, nicht nur dass sich etwas geändert hat
- **Ein Projektcontainer trägt die Geometrieeingaben** einschließlich
  Startwerten und Rückfallstufen. Er erleichtert reproduzierbare Berechnungen,
  garantiert aber keine Reproduktion von Treiber-, Plattform-, Netzwerk-
  oder Lebensdauerfehlern. Der Problembericht aus §37.2 ergänzt Versionen
  und Protokoll; ein Projekt wird nur mit ausdrücklicher Zustimmung beigefügt.

### 16.3 Herkunft importierter Modelle
Heruntergeladene Modelle tragen Lizenzen, oft mit Einschränkung für
kommerzielle Nutzung. Jede Quelle kann `origin` führen: URL, Titel, Urheber,
Lizenz, Abrufdatum. Beim Import anbieten, nicht erzwingen. **Beim Export ein
Hinweis**, wenn eine beteiligte Quelle eine Einschränkung trägt — einmal,
sachlich, ohne Belehrung.

---

## 17. Eingangsstufe und Rückfallketten

### 17.1 Eingangsstufe
Die unveränderte Quelldatei bleibt in `sources` erhalten. Die Op `load`
baut daraus das normalisierte Szenenobjekt über dieselbe Eingangskette:

1. **Einheit bestimmen.** STL kennt keine Einheiten. Heuristik über die
   Bounding Box; bei Verdacht **nachfragen** statt annehmen.
2. **Vertices verschweißen** mit `EPS_GEOM`, skaliert an der Modellgröße.
3. **Entartete Dreiecke entfernen** (Nullfläche, Nadeln, Dubletten).
4. **Normalen vereinheitlichen**, Orientierung prüfen.
5. **Komponenten zählen**, Kleinstteile melden statt still zu löschen.
6. **Lage**: Schwerpunkt ermitteln, Aufsetzen auf das Bett und Zentrieren
   darauf anbieten — nicht erzwingen. **Das erste Modell eines Projekts** kommt
   aufgesetzt und mittig herein (Entscheidung Robert, 03.09.2026): Ein leeres
   Bett hat keine Lage, die zu erhalten wäre, und ein Modell, das halb unter
   der Platte oder weit daneben steht, ist der erste Eindruck eines frischen
   Projekts. Jedes weitere behält seine Lage — es käme sonst in das erste zu
   liegen; dafür gibt es *Auf dem Bett anordnen* (§29). Beides steht als
   Parameter in der Op, nicht als Regel bei der Auswertung.

Die Eingangsstufe ist die Op `load`, damit ihre Parameter im Stack sichtbar und
änderbar bleiben. Verschweißen und Entfernen entarteter Dreiecke dürfen einen
bereits geschlossenen Eingangskörper nicht öffnen. Falls eine Bereinigung das
täte, bleibt der vorherige Körper erhalten und der Prüfbericht nennt den
ausgelassenen Bereinigungsschritt.

### 17.2 Rückfallkette für Boolesche Operationen

| Stufe | Verfahren | Vermerk |
|---|---|---|
| 1 | direkt | `direct` |
| 2 | Vertices verschweißen, entartete Dreiecke entfernen, erneut rechnen | `welded` |
| 3 | minimale Störung der Eingangsgeometrie | `jittered` (+ Startwert) |
| 4 | voxelbasiert rechnen und zurück vernetzen | `voxel` |
| 5 | Abbruch mit Befund und Handlungsvorschlag (§2.7) | — |

Die erfolgreiche Stufe steht in der Op. Stufe 4 kostet Genauigkeit und wird im
Prüfbericht ausgewiesen, nicht stillschweigend verwendet. In Entwurfsqualität
(§31) endet die Kette nach Stufe 2, um Iterationen schnell zu halten.

### 17.3 Prüfbericht
Alles aus §17.1 und §17.2 landet in einem Bericht je Objekt, sichtbar im
rechten Bereich, im Steckbrief und in `report.json`. Der Agent muss wissen,
dass er auf einem voxelgeglätteten Ergebnis arbeitet.

---

## 18. Der Viewport

Der Viewport ist Anzeige- und Prüfwerkzeug. Er zeichnet über den gemeinsamen
Renderervertrag mit **pygfx/wgpu**. Es gibt keine Rendererwahl; die verbliebene
VTK-Nutzung im Kern ist ausschließlich Geometrie der Baustein-Bereichsprüfung
und kein alternativer Zeichenweg.

### 18.1 Darstellung
Massiv, Drahtgitter, Massiv+Kanten, transparent. Flache und weiche
Schattierung. Orthografisch und perspektivisch — orthografisch ist beim Messen
Pflicht. Sieben Kameravoreinstellungen. Rückseiten eingefärbt, damit
invertierte Normalen auffallen.

### 18.2 Schnittebene
Ebene an X/Y/Z oder frei, interaktiv verschiebbar, optional zweite Ebene für
eine Scheibe, Schnittkontur mit Maßangaben.

**Die Schnittfläche wird geschlossen dargestellt** (Capping). Ohne Deckel wirkt
jedes Volumen hohl und Wandstärken sind nicht beurteilbar — daran scheitern
naive Umsetzungen.

### 18.3 Messen
Punkt-zu-Punkt mit Fang auf Vertices und Kanten. **Durchmesser über
Feature-Auswahl**, nicht über drei geklickte Punkte. Winkel zwischen erkannten
Ebenen. Wandstärke am Klickpunkt. Bounding Box und Volumen der Auswahl.
Bemaßungen bleiben stehen, bis sie gelöscht werden; Anzeige gerundet auf
`EPS_DISPLAY`.

### 18.4 Analysekarten

| Karte | Zeigt | Nutzen |
|---|---|---|
| Wandstärke | Verlauf, dünn hervorgehoben | zu dünne Stellen finden |
| Überhang | Winkel gegen Z, > 45° hervorgehoben | Stützbedarf, Orientierung |
| Netzfehler | offene Kanten, Non-Manifold, Durchdringung | Reparaturbedarf |
| Krümmung | Krümmungsradius in Millimetern, scharfe Kanten gesondert markiert; gemessene Merkmalswerte und Schätzung unterschieden | Feature-Erkennung und Rundungsmaße prüfen |
| Feature-Zuordnung | jedes Feature eigen eingefärbt | verstehen, was die KI sieht |
| Passungen | verbundene Paare, Verletzungen markiert | Mehrteiliges prüfen (§14) |
| Stützbedarf | geometrische Schätzung aus der Schichtanalyse (§22); G-Code-Kennwerte werden getrennt gegenübergestellt (§28) | Orientierung beurteilen |

Immer mit Legende und Zahlenbereich, Paletten nach §19.1. Jede Karte ist auch
über den Prüfbericht erreichbar: Klick auf eine Warnung schaltet die passende
Karte ein und fährt die Kamera auf die Stelle — der kürzeste Weg von „es gibt
ein Problem" zu „hier ist es".

### 18.5 Feature-Overlay
Erkannte Merkmale tragen übersetzte, verständliche Namen und Maße, etwa
„Bohrung 3 · Ø4,2 mm“ oder „Oberseite“. Technische Kennungen bleiben für
Referenzen und Rückverfolgung erhalten, sind aber kein Ersatz für den
sichtbaren Namen. Merkmale werden beim Überfahren hervorgehoben und beim
Anklicken ausgewählt; sie dienen als Referenz im Chat und öffnen ein
Kontextmenü mit den passenden Ops (§10, `applies_to`).

Diese Brücke zwischen Maus und Sprache ist die wichtigste Einzelfunktion der
Anwendung: Der Nutzer muss keine Feature-Namen kennen, er zeigt hin.

#### Die Auswahl hat eine Tiefe, und die Maustasten teilen sie sich

**Der Linksklick wandert:** Der erste wählt den Körper, der nächste das Merkmal
darunter. Innerhalb eines Körpers bleibt man drin — die nächste Bohrung kostet
einen Klick, nicht zwei; ein anderer Körper fängt von vorn an. Escape geht eine
Stufe zurück.

**Der Rechtsklick geht nicht gestuft**, und das folgt aus der Zusage darüber:
Wenn das Kontextmenü am Merkmal der Ort für Weg 1 ist — indem man auf die
Stelle zeigt, die stört —, dann darf es nicht an einer Vorbedingung hängen, die
niemand kennt. Er trifft immer das Genaueste unter dem Zeiger.

**Solange ein Operationsdialog nach einem Merkmal fragt, gibt es keine Stufen.**
Ein Klick ist dann eine Antwort und keine Navigation.

Wie das im Einzelnen geschieht — welche Methode was entscheidet, mit welcher
Reichweite ein Klick ein Merkmal trifft, welche Zahlen dabei gemessen wurden —
steht in der Gebietsregel zur Oberfläche. Hier stehen die drei Zusagen; dort
steht der Weg.

### 18.6 Druckbett und Bauraum
Bett als Gitter im realen Maß, Bauraum als transparente Box, Objekte außerhalb
markiert, Kollisionen markiert, Schwerpunkt und Aufstandsfläche einblendbar.

### 18.7 Vorher/Nachher
Vorheriger Stand als halbtransparenter Geist. **Differenzansicht**: entferntes
und hinzugefügtes Volumen unterschieden — Farbwahl nach §19.1, zusätzlich über
Muster kodiert. Schieberegler über den Verlauf. Bezugsgröße ist die
Transaktion, nicht die Einzel-Op.

### 18.8 Objektbaum
Sichtbarkeit, Isolieren, Umbenennen, Farbe, Herkunft (aus welcher Op und
Transaktion), Kennzeichnung Mesh oder B-Rep. Bei Split-Ergebnissen eine
**Explosionsansicht**.

### 18.9 Darstellungsleistung
Für die Anzeige dezimierte Version ab der Schwelle aus §31; das Original bleibt
für die Berechnung unangetastet. Analysekarten verzögert im Hintergrund mit
Fortschritt. Die Dezimierung darf nie in den Geometriekern zurückfließen.

### 18.10 Schichtenvorschau
Durch die Höhe scrubben, Querschnitt und Konturen sehen, Inseln hervorgehoben
(§22.4). Ehrlich beschriftet als „Schichtanalyse", nicht als „Vorschau" — sie
zeigt Geometrie, keine Werkzeugwege.

### 18.11 Direktmanipulation
Gizmo zum Verschieben, Drehen, Skalieren. Snapping: Fläche an Fläche, Achsen
ausrichten, Bohrungsachsen zur Deckung bringen, Raster- und Winkelfang.
**Jede Manipulation erzeugt eine Op.** Zahleneingabe während des Ziehens.

---

## 19. Bedienung und Barrierefreiheit

### 19.1 Farbe trägt nie allein die Bedeutung
Die Differenzansicht ist die wichtigste Ansicht der Anwendung — ausgerechnet
sie hätte in Rot/Grün die für Farbfehlsichtigkeit schlechteste Kombination.

- **Vorgabe ist Blau/Orange.** Rot/Grün und Graustufen-mit-Schraffur stehen
  als Alternativen zur Wahl.
- Zusätzlich zur Farbe immer eine zweite Kodierung: Muster, Schraffur, Symbol
  oder Beschriftung.
- Analysekarten benutzen wahrnehmungsgleiche Paletten (Viridis-Art), keinen
  Regenbogen — der erzeugt Kanten, wo keine sind.

### 19.2 Tastatur
Jede Op kann ein Kürzel führen; der Konsistenztest lehnt Dubletten ab. Die
**Befehlspalette** ist der Universalzugang. Der Viewport ist mit der Tastatur
navigierbar (Achsansichten, Zoom, Auswahl durchblättern). Undo und Redo gelten
überall, auch im Chat.

### 19.3 Anzeige
HiDPI-tauglich, skalierbare Schriftgröße, ausreichender Kontrast in hellem und
dunklem Thema. **Anzeigeeinheit umschaltbar** zwischen Millimeter und Zoll —
der Kern bleibt bei Millimeter (§11.1).

---

## 20. Farbe und Multi-Material

**Datenmodell**: pro Objekt eine Liste von Materialslots, pro Dreieck ein
Slot-Index als Face-Attribut, optional UV und Textur aus Säule B. Der Slot ist
das Dateiformat; die Bedienung nennt **Filament mit Name, Typ und Farbe**, nie
eine nackte Nummer. Der projektübergreifende Filamentkatalog darf beliebig
viele Spulen führen, je Objekt gelten höchstens acht gleichzeitig benutzte
Slots. Die aktuell im Slicer eingelegten Filamente werden samt Typ, Farbe und
Herstellerprofil als Vorwahl übernommen; ein von Hand angelegtes Filament
lässt seinen Typ ausdrücklich wählen.

**Import**: STL keine Farbe (alles Slot 0), 3MF Materialgruppen je Dreieck,
OBJ+MTL Gruppen und optional Textur, GLB/glTF ein PBR-Material mit Textur,
STEP keine Farbe aber echte Flächen (§30).

**Von der Textur zum Druck**: zurückprojizieren, auf die Anzahl geladener
Filamente quantisieren (k-Means, **mit gespeichertem Startwert**), glätten
gegen Einzeldreieck-Sprenkel, als Slots ablegen, nach 3MF exportieren. Nie so
fein wie das Rendering — klar kommunizieren.

**Attributerhalt**: Boolesche Operationen dürfen die Slot-Zuweisung nicht
verlieren. `manifold3d` kann Eigenschaften hindurchreichen; wo das nicht
greift, über Nächste-Fläche-Zuordnung übertragen. Neue Schnittflächen bekommen
einen konfigurierbaren Slot. **Nach Rückfallstufe „voxel" ist die Zuweisung
immer neu zu übertragen**, weil die Vernetzung ersetzt wurde.

**Zuweisen** geschieht in zwei reproduzierbaren Operationen: *Teil färben*
weist dem ganzen Körper ein Filament zu, *Fläche färben* genau einer erkannten
Fläche. Die Flächengrenze kommt aus der Merkmalserkennung und wandert bei
Maßänderungen mit. Der frühere Punkt-Radius-Pinsel ist seit Formatversion 14
ausgebaut; sein gespeicherter Punkt konnte keine stabile Fläche benennen.

**Druckwerte je Filament** dürfen Temperatur, Kühlung, Rückzug und
Materialwerte übersteuern — nur Eigenschaften der Spule, keine Geometrie. Name,
Farbe und Werte bleiben beim direkten 3MF-Export und bei der Slicer-Übergabe
demselben Extruder zugeordnet, auch über mehrere Platten.

---

## 21. Feature-Erkennung und stabile IDs

### 21.1 Was erkannt wird
Bohrungen (Zylinderflächen clustern → Durchmesser, Achse, Tiefe, Durchgang oder
Sackloch), Zapfen (dieselbe Suche, andersherum gelesen), **Kegel** (Senkung,
Fase an einer Bohrung, Verjüngung → Öffnungswinkel, Achse, Mitte, Durchmesser),
**Kugeln** (Pfanne oder Kuppel → Mittelpunkt, Durchmesser), **Tori** (Kehle
oder Wulst → Achse, Mitte, Ring- und Röhrendurchmesser), **Verrundungen** an
geraden Kanten (→ Radius, Achse, Länge), ebene Flächen
(koplanare Cluster → Normale, Fläche, Schwerpunkt, Randkontur), Randschleifen
(offene Kanten = Defekte), Symmetrieebenen, Dünnstellen,
Zusammenhangskomponenten. Gewinde werden über nachgewiesene Helices erkannt:
Achse, Steigung, Durchmesser, Länge sowie Innen- oder Außengewinde. Zusammengehörige
Gewindegänge werden nicht zusätzlich als einzelne Bohrungen, Kegel oder Tori
angeboten.

**Ein Fleck endet an einer Kante, nicht am Zusammenhang.** Das klingt nach einer
Feinheit und war der Grund, weshalb eine **gesenkte Bohrung überhaupt nicht in
der Szene stand** — nicht die Senkung fehlte, die ganze Bohrung. Kegelwand und
Bohrungswand hängen aneinander; als ein Fleck gelesen passt darauf kein
Zylinder, und heraus kam nichts. Getrennt wird an derselben Schwelle, die eine
Rundung von einer Kante trennt (30 Grad): Der Übergang Bohrung → 90°-Senkung ist
ein Knick von 45 Grad, die Facetten eines gebohrten Zylinders liegen bei vier.

**Welche Form ein Fleck ist, entscheiden die Normalen — nicht der Rückstand
einer Einpassung.** Bei einem Zylinder stehen sie senkrecht auf der Achse, bei
einem Kegel um `sin` des halben Öffnungswinkels daneben; das ist eine
Eigenschaft und kein Gütemaß. Der Rückstand kann es nicht entscheiden, und der
Fall, der das zeigt, ist ein aufgesetzter Kegel: Jede Facette ist **ein** Dreieck
von der Grundfläche zur Spitze, ihr Schwerpunkt liegt auf einem Drittel der
Höhe — also liegen alle Schwerpunkte auf einem Kreis, und die
Zylindereinpassung findet einen tadellosen Zylinder mit Rückstand null an einem
Kegel mit 31 Grad. **Die Form kommt aus dem Winkel, die Güte aus dem
Rückstand**, und ein Zylinder bleibt einer, solange er unter fünf Grad steht:
Ein `hole_1`, das plötzlich `cone_1` hieße, wäre für jede Bohrungs-Operation
unsichtbar.

**Ein Zylinderausschnitt ist keine Bohrung und kein Zapfen, sondern eine
Verrundung.** Getrennt wird an der Überdeckung um die Achse: Bohrungen und
Zapfen überdecken 345 bis 356 Grad, eine verrundete Quaderkante 90 — dazwischen
liegt über den ganzen Korpus nichts. Ohne diese Trennung las der Kunde „Zapfen
Ø 6" an dem, was er als „Verrundung R 3" kennt, und `applies_to` bot ihm
Passungs-Operationen an; §14 nennt einen Zapfen aber das, womit man eine
Bohrung paart, und mit einer Kantenverrundung paart niemand etwas.

**Verrundungen und Torusflächen bleiben unterschiedliche Merkmalsarten.**
Eine zylindrische Verrundung an einer geraden Kante wird als `fillet` mit
ihrem Radius erkannt. Eine Verrundung an einer runden Kante kann als
ausreichend bestimmtes Torusstück erkannt werden; ihr Radius ist der halbe
`tube_diameter`. Die Torusform allein belegt nicht, dass die Fläche als
Kantenverrundung konstruiert wurde. Sie bleibt deshalb ein `torus`-Merkmal;
`recess` unterscheidet Kehle und Wulst.

**Die Reihenfolge der Prüfungen ist Teil der Aussage.** Kugel und Torus kamen
am 22.08.2026 dazu, und sie werden erst gefragt, wenn Zylinder und Kegel
abgelehnt haben — nicht daneben. Der Fall, der das erzwingt: Eine 90°-Senkung
passt auf eine **Kugel** mit einem Rückstand von 0,054 und damit unter der
Schwelle, die für Zylinder und Kegel gilt; eine echte Kalotte liefert 0,0003.
Deshalb steht dort eine eigene, strengere Schwelle (`ROUND_TOLERANCE`, 0,02),
und deshalb kommt die Frage zuletzt. Ein `hole_1`, das plötzlich `sphere_1`
hieße, wäre für jede Bohrungs-Operation unsichtbar.

Ein kleiner Fit-Rückstand allein macht eine Fläche noch nicht bearbeitbar.
Kugel-, Torus- und Kegelflächen müssen auch durch ihre lokale Krümmung,
Normalen und räumliche Ausdehnung bestimmt sein. Ein unsicherer Fit darf bei
der Formauswahl einen noch schlechteren verdrängen, ohne selbst als sicheres
Merkmal veröffentlicht zu werden.

**Auch ein Torusstück kann beide Radien liefern.** Die Einpassung bestimmt
die Achse aus den Normalen, den Achsenpunkt aus einem zweiten linearen System
und beide Radien aus dem Meridiankreis. Eine feste Mindestüberdeckung gilt
dabei nicht allgemein. Veröffentlicht wird ein Merkmal nur bei ausreichend
bestimmter Einpassung, geeigneter räumlicher Ausdehnung und zur Torusfläche
passenden Normalen. Ein kleiner Punktabstand allein genügt nicht; unsichere
Ausschnitte werden nicht als gesicherte Torusmerkmale angeboten.

**Ein Fleck endet an einer Kante — oder an einem Sprung der Krümmung.** Das
Zweite kam am 22.08.2026 dazu, und der Fall, der es erzwingt, ist eine
Verrundung: Sie schließt **tangential** an, das ist ihr Zweck, und ein Knick
trennt sie deshalb nicht ab. An einer Säule Ø 12 mit R 3 am Fuß lagen Mantel
und Kehle in **einem** Fleck, auf den weder ein Zylinder noch ein Torus passte
— das Alltagsteil hatte keine Mantelfläche, auf die der Agent hätte zeigen
können. Getrennt wird am Verhältnis der Krümmungsradien; die Schwelle ist
gemessen und nicht gewählt (über den Korpus liegen alle Sprünge innerhalb
einer Fläche unter 0,31, der an einer Verrundung bei 0,80).

**Nachgetrennt wird erst, wenn keine Form gepasst hat**, und nie davor. Ein
Kegel hat keine feste Krümmung — sein Querradius wächst stetig —, und
grundsätzlich nachgetrennt zerfiel im Beispielprojekt *Aushöhlen und Teilen*
eine Senkung in zwei Kegel. Weil zwei gespiegelte Senkungen für die Zuordnung
gleich aussehen, hielt die Auswertung an und fragte den Nutzer viermal, welches
Merkmal `cone_1` entspricht — in einem mitgelieferten Beispiel. Was erkannt
wurde, bleibt deshalb, wie es ist; es kommt nur dort etwas dazu, wo bisher
nichts war.

### 21.2 Das ID-Problem
**Erzeugte Features — Provenienz.** Was eine Operation selbst erzeugt, trägt
den Schritt, der es erzeugte, in einem eigenen Feld: `created_by`. Keine
Erkennung, keine Mehrdeutigkeit. Mit
der Bausteinbibliothek (§24) wächst dieser Anteil deutlich.

**Nicht über die ID.** Bis zum 22.08.2026 stand hier eine abgeleitete Kennung
(`op4.pin_1`) — sie wurde im Produktivcode nie vergeben und nie gelesen, sie
stand allein in Tests, die sie von Hand hinschrieben. Entschieden wurde
dagegen, und der Grund ist dieser Abschnitt selbst: Die ID ist der Schlüssel,
an dem spätere Operationen hängen, und sie trägt schon eine Bedeutung. Ihr eine
zweite aufzuladen machte jede Änderung am Erzeuger zu einer Umbenennung — und
verlangt wird hier gerade Stabilität. Ein eigenes Feld sagt eine Sache, bleibt
leer, wo niemand es füllt, und lässt alte Projektdateien unberührt.

**Gesetzt wird es einmal, beim Entstehen.** Wer ein Merkmal durchreicht, hat es
nicht erzeugt. Das ist der Unterschied zu `SceneObject.created_by`, das bei
jeder Operation neu gesetzt wird, die das Objekt ausgibt, und deshalb auf die
zuletzt beteiligte zeigt statt auf die erzeugende.

**Ein erzeugtes Merkmal bietet immer mindestens eine Handlung an: den Schritt
zu ändern, der es erzeugt hat.** Das ist der Ausweg aus einer Sackgasse, die
sonst an jeder Merkmalsart einzeln entsteht — ein fertiges Gewinde ist der
Fall, an dem sie aufgefallen ist: Auf ein Gewinde passt keine der Operationen
aus §25, also bot das Kontextmenü nichts an, obwohl das Gewinde einen Erzeuger
mit Parametern hat. Über `applies_to` (§10) wäre das nur mit einer neuen
Operation je Merkmalsart zu beheben. Über die Provenienz ist es ein Eintrag,
der für alle gilt und für neue Merkmalsarten von selbst mitkommt. Bei einem
erkannten Merkmal entfällt er — es hat keinen Erzeuger, und ein Eintrag, der
ins Leere führt, ist schlechter als keiner.

**Importierte Features — Zuordnung.** Nach einer Geometrieänderung werden die
Merkmale des Ergebnisses bestimmt und dem vorherigen Zustand zugeordnet.
Erhaltene, von der Operation benannte Merkmale und eindeutig übertragbare
Transformationen werden dabei weitergeführt. Alt und neu werden über einen
Merkmalsvektor (Typ, Durchmesser, Achsenrichtung, Position im Objektsystem,
Nachbarschaft) optimal zugeordnet: ungarische Methode über die Kostenmatrix,
mit getrennt normalisierten Toleranzen und der Annahmeschwelle
`MATCH_THRESHOLD`. Diese dimensionslose Kostenschwelle ist keine geometrische
Längentoleranz.

Einmal vergebene Kennungen bleiben am Objekt reserviert. Ein verschwundenes
Merkmal gibt seinen Namen nicht für ein anderes frei; bei mehreren Eingängen
wird die Menge der reservierten Kennungen mitgeführt.

| Fall | Verhalten |
|---|---|
| eindeutig unter Schwelle | ID bleibt |
| kein Partner | verwaist |
| mehrere dichte Kandidaten | mehrdeutig |

### 21.3 Verhalten bei Verwaisung
Verweist eine spätere Op auf eine verwaiste oder mehrdeutige ID, **hält die
Auswertung dort an** (§15.3), zeigt die Kandidaten hervorgehoben und fragt über
`ctx.ask`. Der Nutzer wählt, die Op wird umgeschrieben, es läuft weiter. Beim
Öffnen einer Projektdatei werden alle Feature-Verweise einmal geprüft, bevor
gerechnet wird.

---

## 22. Schichtanalyse — der eigene Analyse-Slicer

Bewusst **kein** G-Code-Slicer. Perimeter, Nahtplatzierung, Kühlung,
Retraction, Bridging, Baumstützen und Maschinengrenzen sind fünfzehn Jahre
Arbeit anderer Leute; ein schlechteres Ergebnis kostet das Vertrauen in die
ganze Anwendung. Die Datei, die auf den Drucker geht, kommt weiterhin vom
externen Slicer (§28).

Das **Schneiden zur Analyse** ist dagegen eine überschaubare Sache und der
größere Hebel.

### 22.1 Verfahren
Je Schichthöhe werden die Dreiecke an der Ebene geschnitten und die
Schnittsegmente zu geschlossenen Ringen verkettet. Flächen-, Schnitt- und
Offsetrechnungen laufen über Shapely/GEOS. Der übersetzte Kern `slice/_chain`
beschleunigt Ebenenschnitt und Verkettung; ohne ihn bleibt der NumPy-/GEOS-Weg
verfügbar (§31). Beide Wege müssen geometrisch gleichwertige Konturen liefern.

Die Analyse läuft im eigenen Prozess ohne externen Slicer. Lange Läufe melden
Fortschritt und sind abbrechbar. Für ihre Geschwindigkeit gelten die
korpusbezogenen Ziele aus §31.

### 22.2 Was daraus abfällt

| Größe | Bedeutung |
|---|---|
| Überhangfläche je Schicht | Differenz zur darunterliegenden Kontur |
| Stützvolumen | die Säule unter den Überhängen, von der Unterseite bis zum Material darunter oder zur Platte — nur dieser Raum trifft §40 (auf 1 % genau gegen analytische Körper) |
| Querschnittsverlauf | sprunghafte Änderungen → Verzugs- und Haftungsrisiko |
| **Inseln** | Konturen ohne Verbindung nach unten — brauchen zwingend Stütze |
| Erste Schichtfläche | Haftung und Kippstabilität |
| Brückenweiten | freitragende Strecken je Schicht |
| Kleinste Strukturbreite | gegen Düsendurchmesser prüfbar |

### 22.3 Was sich dadurch ändert
Der eigentliche Gewinn ist nicht die Ersparnis, sondern der Maßstab:

- **Orientierungssuche**: viele Kandidaten intern bewerten und die aussichtsreichen
  Lagen über das Stützvolumen der Schichtanalyse vergleichen (§28.2). Bericht
  und Messung unterscheiden die Zahl der betrachteten Richtungen von der Zahl
  der tatsächlich geschnittenen Lagen.
- **Trennebene beim Auto Split**: dieselbe Suche über Schnitthöhen und
  -richtungen.
- **Sofortige Rückmeldung**: Überhang- und Inselwarnungen erscheinen im
  Prüfbericht, ohne dass ein Slicer installiert sein muss. Die Anwendung ist
  damit vom ersten Start an beurteilungsfähig.
- **Analysekarten** Überhang und Stützbedarf (§18.4) bekommen echte Werte
  statt einer Normalen-Heuristik.

### 22.4 Schichtenvorschau
Fällt fast gratis ab: durch die Höhe scrubben, Querschnitt und Konturen sehen,
Inseln hervorgehoben. Sie ersetzt keine Slicer-Vorschau — sie zeigt die
Geometrie, nicht die Werkzeugwege — und ist genau deshalb ehrlich zu
beschriften: „Schichtanalyse", nicht „Vorschau".

### 22.5 Abgrenzung

| | eigener Analyse-Slicer | externer Slicer (§28) |
|---|---|---|
| Zweck | suchen, bewerten, warnen | drucken |
| Geschwindigkeit | Ziele nach §31 | abhängig von Modell, Profil und Slicer |
| Ergebnis | Kennzahlen, Konturen | G-Code |
| Voraussetzung | keine | Installation |
| Verbindlich für | Iteration und Optimierung | die Druckdatei |

Die Kennzahlen beider Wege werden **nie vermischt**. Der Prüfbericht weist
aus, woher ein Wert stammt. Das Stützvolumen der Schichtanalyse beschreibt
Stützraum; das aus G-Code ermittelte Stützmaterialvolumen beschreibt geplante
Extrusion. Für eine Gegenprobe müssen Dichte, Einheit und zugrunde liegende
Profile vergleichbar sein; keines von beiden ist eine Messung am gedruckten
Werkstück.

---

## 23. Steckbrief für den Agenten

```
Szene: 2 Objekte, Drucker centauri-carbon-2, Material PETG (kalibriert)
Parameter: breite=84.0 mm, hoehe=22.0 mm, wandstaerke=2.4 mm
Auswahl: obj_2 · hole_3
obj_2  "halterung_oben"  84 × 40 × 11 mm, 14.1 cm³, wasserdicht, auf Bett
  face_1  planar 84×40, Normale -Z   (Aufstandsfläche)
  hole_3  Ø 5.2 mm, Achse +Z, Durchgang, auf face_1
  heatset_1  Baustein heatset_m4, auf face_1, created_by=op3
  pin_1      Ø 4.0 mm, Achse +Z, Zapfen, created_by=op5   → Passung stift_1
  hinweis Op 5 über Rückfallstufe "voxel" gelöst — Genauigkeit eingeschränkt
  warnung Dünnstelle 0.9 mm nahe face_7
obj_3  "halterung_unten" …
Stack: t1 "Import und Reparatur" (Ops 1–2, Nutzer) ·
       t2 "Teilen und verstiften" (Ops 3–6, Agent)
```

Dazu die gerenderten Ansichten — beschriftete PNG-Bilder (schräg oben und
von oben), gerendert von der Oberfläche, denn der Kern rastert nicht. Sie
erreichen nur ein Backend, das Bilder versteht; an jedes andere entfallen
sie ersatzlos, und der Steckbrief trägt allein — Bilder sind Zugabe, nie
Voraussetzung (Leitprinzip 8). Der Agent referenziert ausschließlich diese
Namen.

---

## 24. Bausteinbibliothek und Normteile

**Der Agent setzt geprüfte Bausteine zusammen, statt Geometrie zu erfinden.**

### 24.1 Bausteine in Python
```python
@register_part(
    name="heatset_m4",
    title=_("Heat-Set-Einpressbuchse"),
    group="fasteners",
    params=HeatsetParams,
    subtractive=True,
    features=["bore", "chamfer"],
    wall=WallRequirement.not_applicable(
        "Der Baustein ist ein abtragender Werkzeugkörper."
    ),
    feature_requirements=(
        FeatureRequirement("bore"),
        FeatureRequirement("chamfer", when="lead_in"),
    ),
    doc=_("Bohrung für eine Einpressbuchse mit Einführfase."),
)
def heatset_insert(params: BaseParams) -> PartResult: ...
```

Bausteine bauen gegen `manifold3d`. Damit hängt `insert_part` an keiner
externen Installation, ist testbar, schemageprüft und liefert
Provenienz-Features — und die GPL-Frage (§36) stellt sich für die Bibliothek
nicht. Ein `to_scad()` je Baustein bleibt als **Ausgabeformat** erhalten: Es
schreibt eine Datei zum Weitergeben und führt nichts aus.

**Erstbestückung**: Schraubenloch mit Senkung, Heat-Set-Einpressbuchse,
Mutternfalle (seitlich und von unten), Magnettasche, Kabeldurchführung mit
Zugentlastung, Schnappverbindung, Rastnase, Filmscharnier, Passstift und
Passbohrung, Wandhalter, Schlüsselloch-Aufhängung, Versteifungsrippe, Gewinde.

### 24.2 Normteiltabelle
Metrische Schrauben (Kern, Durchgang, Kopf, Schlüsselweite), Muttern,
Scheiben, Heat-Set-Buchsen, Magnete, Kugellager, Aluprofil-Nutmaße, Schlauch-
und Rohrmaße. „Loch für M4-Einpressmutter" muss ein Nachschlagewert sein.

Bei Veröffentlichung: Maßangaben als Zahlen sind frei verwendbar, Normtexte
und Normtabellen nicht. Werte aus frei zugänglichen Herstellerangaben
zusammentragen, keine Normblätter abschreiben.

### 24.3 Katalog und Prüfung
Der **Bausteinkatalog** zeigt Vorschaubilder, Kurzbeschreibung und die zwei
wichtigsten Parameter — eine Bibliothek, die man nicht sieht, existiert für
den Nutzer nicht. Die Vorschaubilder werden aus den Bausteinen selbst
gerendert, nicht von Hand gepflegt.

Bei einem neuen oder geänderten Baustein sowie bei veränderten Parametergrenzen
wird der vollständige kartesische Grenzbereich von Hand geprüft: wasserdicht,
Mindestwandstärke, keine Selbstdurchdringung, deklarierte Features vorhanden und
korrekt benannt. Ein Baustein ohne diesen Nachweis gilt als nicht abgenommen.
Die Prüflogik bleibt automatisiert getestet; der vollständige Bereichslauf über
alle Bausteine gehört ausdrücklich nicht zu jedem Torlauf. Der Rezeptdialog
nutzt dieselbe Prüflogik.

Ein Baustein ist dabei **ein** Körper. Seit dem 25.08.2026 gibt es die eine
erklärte Ausnahme (Entscheidung Robert): **print-in-place-Mechanik** darf aus
mehreren Teilen bestehen, wenn der Baustein ihre Zahl am Register deklariert.
Der Bereichstest prüft dann statt der Einteiligkeit die **Druckspalten**
zwischen den erklärten Teilen — je Spalt mindestens das druckbare Spiel aus
dem Materialprofil — und dass die gebaute Teilezahl der Deklaration
entspricht. Was **unerklärt** zerfällt, bleibt ein roter Lauf: Die Ausnahme
gilt der Absicht, nicht dem Versehen.

### 24.4 Versionierung
Die Bibliothek ist Teil des Rechenwegs — also wird sie wie eine Abhängigkeit
behandelt. Ohne das rechnet eine spätere Korrektur an `heatset_m4` alte
Projekte still anders, und Leitprinzip 4 ist verletzt.

- **`parts_version`** in jeder Projektdatei (§16.2)
- **Änderungsverlauf je Baustein**: was, wann, warum, mit Auswirkung auf die
  Maße
- **Beim Öffnen**: Hinweis, welche *benutzten* Bausteine sich seither geändert
  haben, mit der Wahl zwischen „neu rechnen" und „alten Stand beibehalten".
  Eigene Bausteine werden zusätzlich über einen beim Speichern abgelegten
  Inhaltsfingerabdruck je benutztem Baustein erkannt: bei `.py` über den
  Dateiinhalt, bei Rezepten über die Rezeptdaten. Änderungszeit und Dateigröße
  allein belegen keine Inhaltsänderung. Fehlt ein früherer oder aktueller
  Fingerabdruck, ist keine Aussage über eine Änderung möglich. Die grobe
  Invalidierung des Plattencaches (§38) bleibt davon getrennt.
- Der alte Stand bleibt aufrufbar, solange die Bibliothek ihn führt; wird er
  entfernt, verhält sich das wie eine Migration (§16.2)

### 24.5 Eigene Bausteine
Dieselbe Registrierung aus einem Nutzerverzeichnis
(`<Nutzerdaten>/parts/*.py`), beim Start eingelesen, im Katalog eigens
gekennzeichnet.

**Das ist kein Plugin-System.** Der Unterschied ist die Reichweite: Eigene
Bausteine gelten nur auf dem Rechner, auf dem sie liegen.

- Ein eigener Baustein **als `.py` reist nie in einer Projektdatei mit** —
  sonst wäre die Regel aus §32 umgangen, dass eine fremde Datei keinen Code
  ausführt. **Ein Baustein als Rezept darf es** (Entscheidung Robert,
  24.08.2026): Ein Rezept ist ein Ausschnitt des Op-Stapels plus die
  Beschreibung seiner Parameter — Daten, keine Funktion. Es nennt Namen
  registrierter Operationen und Zahlen, und das tut jede Projektdatei ohnehin;
  seine Sicherheitslage ist die einer `project.json`, nicht die einer fremden
  `.py`. Die Erlaubnis gilt **ohne Vorbehalt**, weil kein registrierter
  Parameter mehr Quelltext trägt (§32); entsteht je wieder einer, gilt für ihn
  dieselbe Sperre wie für jeden anderen Weg. Der Katalog weist die Herkunft
  aus, und ein mitgereistes Rezept überschreibt nie einen gleichnamigen
  eigenen Baustein
- **Rezept-Export und -Import bleiben lokal, verlustfrei und offline
  nutzbar.** RS Digital betreibt keine öffentliche Tauschstelle, Galerie,
  Upload-, Download-, Vermittlungs- oder Moderationsfunktion. Nutzer geben
  Bausteindateien ausschließlich über einen selbst gewählten Weg weiter
- Lokale Bausteindateien dürfen erforderliche Modelldaten oder andere
  Payloads mitführen. Solidon prüft Format, Größe, Struktur, Integrität,
  Operationsnamen, Herkunft, Autor und Lizenz vor der Übernahme. Importieren,
  Bearbeiten oder neu Speichern entfernt die fremde Herkunft nicht
- Öffnet jemand ein Projekt, das einen unbekannten eigenen Baustein benutzt,
  hält die Auswertung an und meldet, was fehlt (§15.2)
- Sie erweitern nicht die Anwendung, sondern nur die Bibliothek — keine neuen
  Ops, keine Oberflächenänderungen, kein Zugriff auf den Op-Stack
- Dieselben Tests gelten; ohne bestandenen Parameterbereichstest erscheint ein
  Warnhinweis im Katalog

---

## 25. Operationskatalog

**Szene** — laden (§17.1), duplizieren, löschen, umbenennen, auf Bett anordnen,
Kollision prüfen, vereinigen, in Komponenten zerlegen

**Parameter** — anlegen, ändern, löschen, an eine Op binden

**Passungen** — Paar anlegen, Art ändern, lösen, prüfen

**Reparatur** — Löcher füllen, Non-Manifold entfernen, Normalen
vereinheitlichen, Selbstdurchdringungen auflösen, Kleinstkomponenten löschen,
Vertices verschmelzen

**Transformation** — verschieben, drehen, spiegeln, gleichmäßig und achsweise
skalieren, auf Bett ausrichten, druckoptimal orientieren

**Boolesch** — Vereinigung, Differenz, Schnitt (mit Rückfallkette §17.2);
Primitive einfügen (Quader, Zylinder, Kegel oder Kegelstumpf, Kugel und Ring);
**Baustein an ein erkanntes Feature setzen** (§24)

**Skizze** (§30.1, B-Rep) — Grundform anlegen (Rechteck, Langloch, Kreisbild,
Vieleck), Skizze extrudieren, rotieren, als Tasche schneiden, entlang Pfad
führen, zwischen Skizzenprofilen überblenden

**Formgebung** (B-Rep) — Fase, Verrundung; Formschräge, exakte Schale, Sweep,
Loft, exaktes Gewinde (§30.1)

**Bohrungen** — aufbohren, verschließen, senken, um Materialtoleranz korrigieren

**Druckvorbereitung** — aushöhlen mit Entlüftung, an Ebene schneiden,
Verstiftung setzen, Elefantenfuß kompensieren

**Import** — STL, 3MF (einzeln und als ganze Bauplatte), OBJ, PLY, OFF,
GLB/glTF, STEP/STP (§30); SVG und DXF mit Extrusion

**Farbe** — ein Filament dem ganzen Teil zuweisen, aus einer Textur ableiten
oder eine erkannte Fläche vollständig färben

**Beschriftung** — Text oder Logo erhaben/vertieft auf eine gewählte Fläche

**Oberfläche** — Textur auf eine gewählte Fläche prägen oder einschneiden:
Rippe, Welle, Rändel gerade und gekreuzt, Wabe, Noppen, Voronoi, Rauschen. Als
**echte Geometrie** und als exaktes Gitter, nicht als abgetastetes Höhenfeld —
sonst druckt ein Rändel gerundeten Brei statt scharfer Rauten. Vor dem Bauen
steht die Frage, ob das Muster auf dieser Maschine überhaupt entsteht: Stege
schmaler als die Düse und Prägungen flacher als eine Schicht verschwinden beim
Drucken und werden abgewiesen, nicht gerechnet.

**Netz** — dezimieren, remeshen, glätten

**Varianten** — dieselbe Op-Kette mit durchvariiertem Parameter (§28.3)

**Fasen und Verrundungen benötigen exakte B-Rep-Kanten (§30).** Ein importiertes
Mesh erhält durch den zweiten Kern keine exakte Flächentopologie. Die
Flächenrückgewinnung aus Netzen ist eine gesonderte Entscheidung und keine
Eigenschaft des STEP-Exports.

---

## 26. Agentenschicht

### 26.1 Was der Agent sieht
- **Steckbrief** (§23) einschließlich Projektparameter und **aktueller
  Auswahl** — sonst verpufft der Klick bei „mach das Loch größer"
- **Prüfbericht** einschließlich verwendeter Rückfallstufen
- **Verlauf in Kurzform**: Transaktionen mit Titel, Ops mit Nummer und
  Objekten — sonst kann er „nimm das zurück" nicht ausführen
- **gültige Chatbeiträge** (§26.3), nicht der rohe Verlauf
- **Regelsammlung** in der aktuellen Version (§39)

**Die Reihenfolge ist Teil des Vertrags, nicht Geschmackssache.** Ein Modell
kann den Anfang einer Anfrage zwischenspeichern, aber nur solange dieser Anfang
**Byte für Byte derselbe** ist. Deshalb stehen Werkzeugschemata, Systemprompt
und Regelsammlung vorn — sie ändern sich zwischen zwei Zügen nicht — und
Steckbrief, Prüfbericht, Verlauf und Chat dahinter, weil sie sich in jedem Zug
ändern. Ein Steckbrief im Systemprompt macht das Zwischenspeichern wirkungslos,
und zwar lautlos: Es kommt keine Fehlermeldung, es kommt eine Rechnung. Die Größe des Werkzeugsatzes und seine Token-Grundlast werden mit dem
aktuellen Register und dem tatsächlich verwendeten Modell gemessen.

Zwei Auflagen folgen daraus, und beide gelten ohnehin schon aus einem zweiten
Grund:

- **Die Werkzeugliste hat eine feststehende Reihenfolge** — die des Registers.
  Eine Liste, die in wechselnder Ordnung aus einem Wörterbuch fällt, wäre auch
  ohne Kosten ein Determinismusproblem (Leitprinzip 4).
- **Kein Zeitstempel, keine laufende Nummer, kein Zufallsschlüssel im
  vorderen Teil.** Sie sehen harmlos aus und setzen jeden Zug auf null.

Nachgeprüft wird es an der Rückmeldung des Backends, nicht am Code: Bleibt der
Anteil zwischengespeicherter Eingabetoken über mehrere Züge bei null, hat
jemand vorn etwas hineingeschrieben, das wandert.

### 26.2 Werkzeuge
Alle Ops aus dem Register, dazu:

| Werkzeug | Zweck |
|---|---|
| `ask_user(frage, optionen)` | **Nachfragen statt raten** — Leitprinzip 6 |
| `undo_transaction(id)` | Transaktion zurücknehmen |
| `add_parameter` / `set_parameter` | Projektparameter statt Streuzahlen |
| `add_fit` | Passungspaar anlegen |
| `read_report` | Prüfbericht gezielt nachlesen |
| `find_part(beschreibung)` | passenden Baustein suchen, bevor gebaut wird |
| `read_digest(objekte)` | den Steckbrief mitten im Zug neu lesen — nach mehreren Ops kennt der Agent sonst die IDs nicht, die er selbst erzeugt hat |
| `read_standard(art, größe)` | Normteilmaße nachschlagen statt raten (§24.2) |
| `read_analysis(art, objekte)` | Schichtanalyse, Zeit- und Materialschätzung, Einstellungsrat, Orientierung — nur lesend, mit hartem Größendeckel, Herkunft immer ausgewiesen (§22.5) |
| `set_print_target(drucker, material)` | Projektdrucker und -material wechseln — Toleranzen bleiben Verweise (`auto:<material>`) und rechnen sich mit um |

Ein Werkzeug, das Druckeinstellungen **setzt**, gibt es mit Absicht nicht:
Einstellungen reisen nicht in Transaktionen (§15.5 zieht die Grenze an der
Auswertung), ein Undo nähme sie also nicht mit zurück — und Regel 16 gilt
auch für den Agenten. §28.2 bleibt dabei: „Übernommen wird auf Klick, nie
von allein." Der Agent liest die Vorschläge über `read_analysis`, nennt sie
samt Begründung, und der Klick bleibt im Druckdialog.

`ask_user` ist Pflicht, keine Höflichkeit: Die Agenten-Suite enthält absichtlich
mehrdeutige Anfragen und misst, ob gefragt statt geraten wird.

Diese Liste ist abschließend — was hier nicht steht, gibt es nicht. Die vier
Werkzeuge ab `read_digest` kamen mit der Agent-Vertiefung dazu
(`konzepte/konzept-agent-vertiefung.md`); sie öffnen keinen zweiten Weg ins Dokument:
die lesenden rechnen auf der Arbeitskopie, die schreibenden reisen als Teil
der einen Transaktion des Vorschlags (§26.5, Regel 16).

### 26.3 Chat und Verlauf
**Ein Chatbeitrag mit übernommenen Änderungen verweist auf die zugehörige
Transaktion.** Wird sie zurückgenommen, gilt der Beitrag als **verworfen** und
geht beim nächsten Kontextaufbau höchstens als „wurde verworfen" mit; Redo
stellt ihn wieder her. Reine Antworten und Rückfragen erzeugen keine
Scheintransaktion.
In der Oberfläche werden verworfene Beiträge ausgegraut, nicht gelöscht.

Ohne diese Kopplung argumentiert der Agent nach jedem Undo mit einem Zustand,
den es nicht mehr gibt.

### 26.4 Herkunft
Jede Transaktion trägt `origin`: Urheber, bei Agenten zusätzlich Modell,
Version des Systemprompts, Version der Regelsammlung und Temperatur. Da die
Projektdatei als Fehlerbericht dient, ist das der einzige Weg, später zu
verstehen, unter welchen Bedingungen eine Op entstanden ist.

### 26.5 Ablauf
Vorschlag → Berechnung in Entwurfsqualität → Differenzansicht → Übernahme oder
Verwerfen. Ein Vorschlag ist genau eine Transaktion. Bei eindeutig umkehrbaren
Ops kann die Übernahme automatisch laufen. Iterationslimit und Kostendeckel
sind hart. Nach jeder Op läuft die Prüfung (wasserdicht, Volumen plausibel,
keine unerwarteten Komponenten, keine verwaisten Referenzen, keine verletzten
Passungen); der Befund geht zurück in den Kontext.

**Bausteine vor Primitiven, Parameter vor Zahlen, Fragen vor Raten** — alle
drei im Systemprompt verankert und in der Suite gemessen.

### 26.6 Fernsteuerung über MCP
Ein zweites Programm auf demselben Rechner ruft dieselben Operationen auf wie
die Menüs — über JSON-RPC nach dem Model-Context-Protocol. Die Werkzeuge werden aus derselben Liste wie die des Chats abgeleitet.
Explizite Sperren filtern diese Liste; insbesondere wird `ask_user` ohne
interaktives Gegenüber nicht angeboten. Es gibt keinen zweiten Weg ins
Dokument. Eine gemeinsame Fähigkeit, die vorübergehend nicht fernbedienbar
ist, bleibt als Umsetzungslücke in der Roadmap sichtbar.

Fünf Auflagen, jede mit Test:

1. **Standardmäßig aus**, Schalter in den Einstellungen.
2. **Nur `127.0.0.1`** — geprüft an der Bindung *und* an jeder Anfrage.
3. **Kein ausführbarer Quelltext, kein Dateipfad**, abgewiesen vor der
   Rechnung. Der Pfad wird am Wert erkannt, nicht am Parameternamen.
4. **Jeder Aufruf, der neue Änderungen übernimmt, ist eine Transaktion** mit
   Herkunftsvermerk (§26.4), rücknehmbar wie jede andere. Lesende Werkzeuge
   erzeugen keinen Verlaufsschritt; `undo_transaction` verwendet den
   bestehenden Rücknahmeweg.
5. **Herkunft und Ziel jeder Anfrage werden geprüft.** Ein vorhandener
   `Origin` ist nur für `http`, einen zugelassenen Loopback-Namen und den
   tatsächlichen Serverport erlaubt; fremde Ursprünge und `Origin: null`
   werden mit 403 abgewiesen. Zusätzlich muss `Host` diesen Server benennen;
   ein dort angegebener Port muss stimmen. Diese eigenständige Prüfung
   schützt auch gegen DNS-Rebinding. Eine Anfrage ohne `Origin` darf den
   Origin-Filter passieren, braucht aber weiterhin alle übrigen Prüfungen.

Die Bindung allein belegt weder Herkunft noch Berechtigung. Das Fehlen von
`Origin` ist kein Identitätsnachweis; ein lokaler Nicht-Browser-Client kann
Kopfzeilen selbst setzen.

---

## 27. Backends

**LLM** — Standard ist der eigene Schlüssel des Nutzers im
System-Schlüsselbund. Alternative ist ein lokal erreichbares Ollama-Modell.
Zuverlässiges Tool-Calling wird am konkreten Modell mit der Agenten-Suite
geprüft; Modellwahl, Kontextfenster und Empfehlungen kommen aus der aktuellen
Backend-Konfiguration und den Messungen dazu. Ist kein nutzbares Backend
verfügbar, bleibt der Chat inaktiv und nennt den Einrichtungsweg. Die übrige
Anwendung bleibt benutzbar. Ein lokales Modell benötigt keinen Anbieter-Schlüssel.

**Mesh-Generierung** — der vorhandene Weg verwendet ComfyUI über dessen
HTTP-Schnittstelle, lokal oder an einer vom Nutzer eingetragenen Adresse.
`MeshBackend` bietet `text_to_mesh` und `image_to_mesh`; Eingaben sind Text
beziehungsweise Bildbytes, dazu gespeicherter Startwert, Fortschritt und
Abbruch. Der Vertrag nimmt keinen Nutzercode und keine lokalen Dateipfade an
und hält keinen Projektzustand. Verfügbarkeit und Modellvoraussetzungen
werden vor dem Auftrag geprüft.

**Ein eigener gehosteter Dienst bleibt P11**, abhängig von Nachfrage und einer
neuen Freigabe. Die gemeinsame Backend-Grenze ist kein bereits betriebenes
Solidon-Hosting. Falls der Dienst kommt, nimmt er Text oder Bild und gibt ein
Mesh zurück: keine Projektablage, keine Historie. Eingaben werden nach
Auslieferung gelöscht und nicht für Training verwendet; beides wird dem
Nutzer mitgeteilt. Abrechnung über Guthaben, Warteschlange mit Zeitlimit und
Serverstandort in der EU bleiben die Anforderungen an diese spätere Phase.

---


## 28. Rückkopplung aus Slicer und Drucker

Die Schichtanalyse (§22) sucht und bewertet, der externe Slicer liefert die
Wahrheit für die Druckdatei. Beide Wege bleiben getrennt ausgewiesen.

### 28.1 G-Code zurücklesen
Druckzeit, Materialverbrauch, Stützmaterialvolumen, Schichtzahl und Warnungen
werden aus vorhandenen Slicer-Angaben und den geplanten Werkzeugwegen gelesen.
Fehlende Angaben bleiben unbekannt; sie sind nicht null. Der Prüfbericht nennt
G-Code als Herkunft und unterscheidet die daraus ermittelten Werte von einer
Messung am Drucker. Sie dienen als Gegenprobe zur internen Schätzung und als
Grundlage der Kostenschätzung.

### 28.2 Was das ändert
Die Suche läuft intern über §22. Der externe Slicer prüft die gewählte Lage
mit dem tatsächlichen Druckprofil und liefert Druckdatei und Kostenbasis.
Die Herkunft aller Kennzahlen bleibt erhalten.

**Die Kandidaten folgen der Geometrie.** Vorgesehen sind die Flächennormalen
der konvexen Hülle, nach Fläche geordnet, dazu die sechs Achsrichtungen und die
Normalen der großen ebenen Flächen des Körpers. Die Erzeugung und Reihenfolge
der Kandidaten müssen deterministisch sein; Zufallsrichtungen sind kein Ersatz
für diese Auswahl. Eine Hüllfläche allein beweist noch keine sichere Standlage:
Aufstandsfläche, Schwerpunkt und erforderliche Haftung müssen mitbewertet
werden.

Eine schnelle Vorbewertung darf die anschließende Schichtanalyse auf
begründete Finalisten begrenzen. Ihre Auswahl wird an mechanischen und
organischen Referenzkörpern gegen die vollständig ausgewertete Kandidatenliste
geprüft. Bericht und Leistungsnachweis nennen getrennt betrachtete und
schichtweise ausgewertete Lagen; für 200 betrachtete Kandidaten bleibt das
Zeit- und Abbruchziel aus §31 verbindlich.

Weicht die Gegenprobe deutlich von der internen Schätzung ab, nennt der
Prüfbericht beide Werte samt Herkunft und den abweichenden Vergleich. Zuerst
werden Einheiten, Stützmaterialdichte und Druckprofile abgeglichen; verbleibt
eine systematische Abweichung, wird die Schichtanalyse am zugehörigen Korpusfall
verbessert. Ein externer Wert überschreibt die interne Schätzung nicht.

### 28.3 Selbstkalibrierung
1. Toleranz-Testkörper erzeugen (Zapfen und Bohrungen mit gestaffeltem Spiel,
   Wandstärkenleiter, Überhangfächer)
2. Drucken, nachmessen, Werte eintragen
3. Werte landen im **Materialprofil**, nicht in einem Modell

Weil Toleranzen im Stack Verweise sind (§12), rechnen alle bestehenden
Projekte danach mit den kalibrierten Werten neu.

Dazu der **Varianten-Generator**: dieselbe Op-Kette mit gestaffeltem Parameter
in einem Durchlauf — vier Ausführungen mit 0,10 / 0,15 / 0,20 / 0,25 mm Spiel,
beschriftet, angeordnet. Ein Druck, danach steht der Wert. Mit
Projektparametern ist das ein Aufruf, keine Sonderfunktion.

---

## 29. Export und Slicer-Übergabe

**Umfang**: einzelnes Objekt, aktuelle Auswahl oder ganze Szene.

**Plattenbelegung.** Jeder Körper kommt an die hinterste, dann linkeste freie
Stelle, an die er passt. Reihenfolge und Ergebnis sind deterministisch. Der
Mindestabstand gilt zwischen den Körpern; notwendige Plattenhaftungen werden
zusätzlich berücksichtigt. Der Bauraum und die Zahl verfügbarer Platten sind
Grenzen der Anordnung.

Nicht untergebrachte Körper bleiben im Ergebnis mit einem Befund erhalten;
sie werden nie stillschweigend weggelassen. Eine Änderung des Packverfahrens
wird an denselben Referenzteilen auf Plattenzahl, Kollisionsfreiheit,
Mindestabstände und reproduzierbare Anordnung geprüft.

**Formate**: STL binär, **3MF mit Objektnamen, Anordnung und Farbgruppen**,
OBJ, PLY, GLB zum Zeigen, STEP bei B-Rep-Objekten.

**Namensschema** bei mehreren Teilen, konfigurierbar, Vorgabe
`<projekt>_<objekt>_1von3.stl`. Objektnamen werden dateisystemtauglich
gemacht, ohne unkenntlich zu werden.

**Übergabe an den Slicer**: direkt per Kommandozeile aufrufen oder die
exportierte Datei öffnen. Ordner, Format und Übergabeart werden je Projekt
gemerkt. Solidon benutzt den installierten Slicer als externes Programm und
liefert ihn nicht mit.

Prozesswerte und Filamentzuordnungen werden aus den gespeicherten
Druckeinstellungen des Projekts aufgelöst. Jeder Materialslot verwendet sein
eigenes Materialprofil; ausdrückliche Werte der Spule haben Vorrang. Geerbte
Profile werden über die vollständigen Profilwurzeln des gewählten Slicers
aufgelöst. Format oder Ziel-Slicer dürfen eine nicht unterstützte Einstellung
nicht als erfolgreich übertragen ausgeben; erkennbare Verluste werden vor der
Übergabe benannt. Ausgabe und G-Code-Gegenprobe benutzen dieselbe Auflösung.

**Exportprüfung vor dem Schreiben**, als Bericht, nicht als Blockade:
wasserdicht, innerhalb des Bauraums, keine verletzten Passungen, keine
Dünnstellen unter der Mindestwandstärke, Lizenzhinweis beteiligter Quellen
(§16.3). Wer trotzdem exportieren will, kann das — er weiß dann nur, was er tut.

---

## 30. Zweiter Konstruktionskern (B-Rep)

Der zweite Kern verwendet Open CASCADE über die Python-Bindings OCP:
exakte Flächen und Kanten für **Fasen und Verrundungen**, **STEP-Import und
-Export**, Skizzen mit Zwangsbedingungen und Boolesche Operationen am B-Rep.
Die Darstellung wird daraus vernetzt; diese Tessellierung ist nicht die
Konstruktionsgeometrie.

Als zweiter Kern **neben** dem Mesh-Kern, nicht als Ersatz. Objekte tragen die
Kennzeichnung `kind` (§9). Der Übergang B-Rep → Mesh ist jederzeit möglich, der
Rückweg nicht — im Objektbaum sichtbar machen.

Bei B-Rep-Objekten werden geometrische Merkmale aus der exakten Topologie
abgelesen, statt aus Dreiecken eingepasst. Das löst die Identität nach einer
Topologieänderung nicht von selbst: Provenienz, Zuordnung, reservierte IDs und
Rückfragen folgen auch hier §21. Die Tessellierung arbeitet auf einer eigenen
Kopie des Solids und verändert keine Eingangsgeometrie.

### 30.1 Skizzen mit Zwangsbedingungen

Der Grund für diese Stufe ist eine Produktentscheidung: **so wenig
Fremdprogramme wie möglich.** Das fremde CAD vor dem Import ist der größte
verbliebene Anlass, Solidon zu verlassen — mit Skizzen entsteht ein
Druckteil von der ersten Linie bis zum Export im selben Programm.

- **Eine Skizze ist ein Datenmodell im Kern** (Verträge in §9): Ebene aus
  einer Hauptebene oder einer angeklickten planaren Fläche, Elemente (Linie,
  Bogen, Kreis, Punkt, Spline), Bedingungen (Maß, Koinzidenz, horizontal,
  vertikal, parallel, senkrecht, tangential, symmetrisch, fest, Referenz).
  Kein Qt darunter.

  Ein Spline beschreibt freie Kurven. Eine Referenzbedingung zeigt ein Maß,
  ohne es festzulegen; sie verändert die Freiheitsgrade nicht und erzeugt
  keinen Lösungskonflikt.
- **Die Skizze lebt als Parameterwert der Operation, die sie verbraucht**
  (`sketch_extrude`, `sketch_pocket`, `sketch_revolve`, `sketch_sweep`,
  `sketch_loft`).
  Bearbeiten heißt `change_params` auf dem Schritt im Verlauf — dieselbe
  Regel wie für jede andere Zahl (§15). Es entsteht kein zweiter
  Dokumentbegriff neben dem Stack.
- **Maßbedingungen sind Ausdrücke der Parametergrammatik (§13).** Ein
  Skizzenmaß darf einen Projektparameter benutzen; eine Parameteränderung
  rechnet die Skizze und den Zweig darunter neu. Kein `eval` (Regel 10).
- **Der Solver ist ein eigener numerischer 2D-Solver auf scipy**:
  deterministisch, ohne Zufall. Unterbestimmt meldet die verbleibenden
  Freiheitsgrade als Befund; überbestimmt oder widersprüchlich hält an und
  nennt das kollidierende Bedingungspaar — nie nur „fehlgeschlagen"
  (Regel 17). SolveSpace und py-slvs sind GPL und ausgeschlossen (Regel 15);
  CadQuery oder build123d kommen nur in Frage, wenn die Lizenzprüfung ihrer
  Solver-Abhängigkeiten besteht, und dann als Ersatz des eigenen Solvers,
  nie als zweiter daneben.
- **Der Agent erzeugt Skizzen ausschließlich über benannte Grundformen**
  (Rechteck, Langloch, Kreisbild, Vieleck) und Maße — nie über rohe
  Punktlisten (Leitprinzip 5).
- **Zwei gleichwertige Eingabewege.** Grundformen über Dialog, CLI und Agent
  sowie der grafische Editor im Viewport (Ebene anklicken, zeichnen,
  Bedingungen setzen) erzeugen dieselben parametrischen Skizzendaten. Der
  grafische Editor erweitert die Eingabe; für parametrische Konstruktion
  bleibt er optional. Bedienlogik und Datenübergabe sind offscreen prüfbar;
  Darstellung und tatsächliche Eingabe werden am echten Fenster abgenommen.
- **Die Skizzen-Ops rechnen gegen den B-Rep-Kern.** Ohne installiertes
  `brep` sagen sie das in einem Satz; alles andere bleibt benutzbar
  (bestehendes Muster aus P12).

---

## 31. Leistungsbudget

Die Zielwerte gelten auf dem Referenzkorpus (§34). Jeder Nachweis nennt
Code-Stand, Plattform, Hardware, Modellgröße, Qualitätsstufe, Cache-Zustand und
Messweg. Historische Messwerte sind datierte Prüfberichte und keine dauerhafte
Erledigungsaussage im Bauplan.

| Vorgang | Zielwert |
|---|---|
| Viewport-Navigation | flüssig bei 1 Mio. Dreiecken |
| Anzeigeaufbau, 1 Mio. → 200 000 Dreiecke | unter 4 s |
| Anzeige-Dezimierung greift ab | 500 000 Dreiecken |
| Boolesche Op, 200 000 Dreiecke | unter 2 s |
| Feature-Erkennung, 200 000 Dreiecke | unter 1 s |
| Analysekarte Wandstärke | unter 3 s, im Hintergrund |
| Projekt öffnen aus Plattencache | unter 1 s |
| Parameteränderung → sichtbares Ergebnis | unter 2 s, nur betroffene Zweige |
| Schichtanalyse, 200 000 Dreiecke, 0,2 mm | unter 300 ms |
| Skizzen-Solver, 200 Bedingungen | unter 100 ms |
| Orientierungssuche, 200 Kandidaten | unter 20 s, abbrechbar |
| Anwendungsstart bis bedienbar, **kalt** | unter 3 s |
| Anwendungsstart bis bedienbar, **warm** | unter 3 s |

**Messumfang.** Navigation, Start bis zur Bedienbarkeit und sichtbares Ergebnis
werden am tatsächlichen Fenster mit dem verwendeten Grafikadapter geprüft.
Eine Offscreen-Rechenzeit belegt weder flüssige Navigation noch ein sichtbares
Bild. Die Anzeige-Dezimierung und ihr Aufbau sind zusätzlich getrennt messbar.
Die 500.000 Dreiecke sind die Eingriffsschwelle, kein Zeitwert.
Ein Nachweis der Merkmalserkennung umfasst mechanische und organische
Referenzkörper; ein guter Kugelfall belegt nicht jede Freiform.

Projektöffnen wird durch die Anwendung gemessen: importieren, speichern und in
einer neuen Sitzung wieder öffnen. Ein vorbereiteter Cache-Eintrag allein
belegt den Anschluss des Plattencaches (§38) nicht. Die Zeit enthält Lesen und
Auswertung. Parameteränderungen werden bis zum sichtbaren Ergebnis gemessen;
eine reine Kernzeit ersetzt diesen Ende-zu-Ende-Nachweis nicht.

**Kalt und warm sind getrennte Messungen.** Kalt bezeichnet einen Start ohne
bereits warmen Betriebssystem-Dateicache; warm bezeichnet den wiederholten
Start unter benannten Cache-Bedingungen. Der regelmäßige Torlauf misst den
warmen Weg. Ein neuer Prozess allein beweist keinen kalten Start. Der erste
Geometrieschritt darf erst im sichtbaren Arbeitslauf laden, muss dort aber
Rückmeldung und Abbruch ermöglichen (§2.8).

**Zielerfüllung und Regressionswächter sind verschiedene Aussagen.** Die
absoluten Sicherungen in `tests/test_performance.py` sind teilweise weiter als
diese Produktziele. Ein grüner Leistungslauf belegt deshalb nicht die Tabelle.
Für die Abnahme werden die tatsächlichen Messwerte gegen die jeweiligen
Ziele gelesen; aus einem alten Bestwert folgt kein aktueller Nachweis. Die
Zielwerte werden nicht durch langsameres Ist-Verhalten ersetzt.

**Zwei Qualitätsstufen** werden im `OpContext` durchgereicht: **Entwurf** beim
Iterieren und in der Vorschau (gröbere Auflösung, Rückfallkette endet nach
Stufe 2, genäherte Analysekarten), **Fein** beim Export und im finalen
Prüfbericht. Der Agent arbeitet in Entwurfsqualität und schaltet beim
Abschluss um.

**Der übersetzte Schichtkern gehört zur Auslieferung.** Die Schichtziele
gelten mit `slice/_chain`. Suite und Paketierung bauen ihn für ihre Plattform;
ein Auslieferungspaket ohne Kern wird mit Handlungsvorschlag abgewiesen.
Im Quellklon bleibt der NumPy-/GEOS-Weg verfügbar. Beide Wege müssen
gleichwertige Geometrie liefern; Geschwindigkeit ersetzt keine
Konturvalidierung.

**Regressionsprüfung.** Messwerte bleiben je Maschine und Aufrufkontext
getrennt. Verglichen wird gegen den Median der letzten fünf Läufe, sobald
mindestens drei Vergleichswerte vorliegen. Maßgeblich ist der Median vor dem
Hinzufügen des aktuellen Laufs. Eine Verschlechterung um mehr als 25 Prozent
gilt nach zwei aufeinanderfolgenden Überschreitungen als Regression. Die
Messhistorie wird nicht gegen einen einzelnen jemals erreichten Bestwert
geführt.

Ein roter Leistungstest wird nach Ursache eingeordnet: absolute Sicherung,
Produktziel oder relative Regression. Fremdlast, Cache und Aufrufkontext
werden geprüft; eine vermutete Regression wird unter ruhigen, vergleichbaren
Bedingungen erneut gemessen. Ein Lastausreißer allein belegt keinen
Codefehler. Ein unerfülltes Produktziel oder ein ungeklärter roter Lauf wird
dadurch aber nicht zu einem Erfüllungsnachweis; die Entscheidung samt
Messwerten bleibt dokumentiert.

---

## 32. Sicherheit lokaler Ausführung

Weil Projektdateien als Fehlerbericht weitergegeben werden, wandern sie
zwischen Leuten. Eine fremde Datei darf nichts ausführen.

- **Keine absoluten Pfade** in Projektdateien
- **Parameterausdrücke** über eigenen Auswerter mit beschränkter Grammatik —
  **kein `eval`**, auch nicht abgesichert
- **Kein fremder Quelltext wird ausgeführt** — weder aus einer Projektdatei
  noch aus dem LLM. Es gibt keinen Weg dorthin: Keine registrierte Operation
  nimmt Quelltext als Parameter, und kein Unterprozess bekommt welchen. Die
  Zusage steht als **Sperre** für jeden künftigen Weg — wer einen baut, baut
  die Prüfung mit
- **Jedes externe Werkzeug benutzt die gemeinsame Prozessgrenze**:
  ausdrücklicher Arbeitsordner, getrimmte Umgebung und eigene Prozessgruppe.
  Für Aufrufe, auf deren Antwort Solidon wartet, gelten Zeit- und
  Ausgabegrenzen; Abbruch beendet den Prozessbaum. An den Nutzer übergebene
  Slicerfenster, Dienste und Installer dürfen nach dem Start weiterlaufen
  (§28, §29, §37.2); sie behalten Umgebung, Arbeitsordner und Prozessgruppe,
  aber keine künstliche Lebensdauer des ursprünglichen Aufrufs.
  **Keine Speichergrenze**: Der Nutzerrechner bestimmt den verfügbaren
  Speicher, Solidon erzwingt kein Adressraumlimit für fremde Programme
- **Warnhinweis beim Öffnen** einer fremden Datei mit externen Verweisen —
  nicht mehr, weil etwas laufen könnte, sondern damit der Nutzer weiß, woher
  der Inhalt stammt
- **Prüfsummen** aller Quellen beim Laden verifizieren
- **Grenzen beim Öffnen**: Dreieckszahl, Dateigröße und entpackte Größe
  werden vor großen Allokationen gedeckelt, mit klarer Meldung und
  Handlungsvorschlag. Das gilt an jedem Eingang, auch für 3MF und den
  ZIP-basierten Projektcontainer; die gepackte Dateigröße ersetzt keine
  Grenze für entpackte Inhalte
- **Eigene Bausteine als Python-Code (§24.5) reisen nie mit.** Ein Projekt
  verweist auf sie namentlich; fehlt der Baustein, hält die Auswertung an.
  Ausführbarer Code kommt ausschließlich aus Installation und
  Nutzerverzeichnis. **Bausteine als Rezept dürfen mitreisen**: Sie bestehen
  ausschließlich aus registrierten Operationen und Werten, die keinen
  fremden Quelltext ausführen. Ihre Herkunft bleibt erkennbar.

---

## 33. Fehler und Protokollierung

### 33.1 Ausnahmehierarchie
```text
AppError                     # Basis, trägt Titel, Ursache, Handlungsvorschläge
├── UserError                # Eingabe war unzulässig — korrigierbar
│   ├── ValidationError      # Schema verletzt
│   ├── AmbiguityError       # mehrdeutig, braucht eine Entscheidung
│   └── UnitUnknownError     # Einheit nicht bestimmbar
├── GeometryError            # Geometrie ließ es nicht zu — mit Vorschlag
│   ├── NotManifoldError
│   ├── BooleanFailedError   # trägt die versuchten Rückfallstufen
│   └── OutOfBuildVolume
├── ExternalToolError        # Slicer, ComfyUI, LLM
└── InternalError            # Programmfehler — Fehlerbericht anbieten
```

**Die Regel:** Ein Programmfehler darf nie wie ein Bedienfehler aussehen — und
umgekehrt. `UserError` und `GeometryError` erscheinen als Vorschlag nach §2.7,
`InternalError` als Fehlerdialog mit Berichtsangebot, `ExternalToolError` mit
Hinweis auf die Einstellung, in der das Programm konfiguriert wird.

Jede Anwendungsausnahme trägt `suggestions: tuple[Action, ...]` — anklickbare Handlungen, keine
Prosa. Eine Ausnahme ohne Vorschlag ist unfertig.

### 33.2 Protokoll
Rotierende Datei im Nutzerverzeichnis, rein lokal. Format: Zeitstempel, Ebene,
Modul, Nachricht, Op-Nummer wo zutreffend. Kein Versand von sich aus — die
Abgrenzung zur verbotenen Telemetrie ist: Das Protokoll verlässt den Rechner
nur, wenn der Nutzer es selbst an eine Rückmeldung hängt und diese absendet
(§37.2). Kein Zeitgeber, kein Fehlerpfad und kein Start schickt es.

Ebenen: `debug` nur bei gesetztem Schalter, `info` für Op-Läufe und
Dateizugriffe, `warning` für Rückfallstufen und Befunde, `error` für
Ausnahmen. Keine Geometriedaten ins Protokoll, nur Kennzahlen.

---

## 34. Referenzdaten und Testkorpus

Ohne festen Datensatz sind die Abnahmekriterien nicht prüfbar. Der Korpus liegt
unter `tests/data/`. Die kleinen Referenzdateien und ihre Erzeuger sind Teil
des Repositorys; große deterministisch erzeugbare Leistungsdateien dürfen
lokal entstehen.

Netze liegen unter `tests/data/meshes/`, Projektdateien unter
`tests/data/projects/`. Der Grundkorpus wird mit
`python tests/data/make_corpus.py` erzeugt; zusätzliche Projekt- und
Regressionsdateien werden mit ihrem jeweiligen Erzeuger und Prüfzweck in
`tests/data/README.md` beschrieben. `dense_1m.stl` entsteht beim ersten
Leistungslauf und wird wegen seiner Größe nicht eingecheckt.

| Datei | Zweck |
|---|---|
| `cube_clean.stl` | Grundfall: wasserdicht, 12 Dreiecke |
| `plate_holes.stl` | vier Bohrungen bekannter Größe — Feature-Erkennung, Messen |
| `plate_holes_twin.stl` | zwei identische Bohrungen dicht beieinander — Mehrdeutigkeit |
| `bracket_inch.stl` | in Zoll gespeichert — Einheitenerkennung |
| `plate_cm.stl` | in Zentimetern, Einheit mehrdeutig — die Rückfrage statt der Annahme |
| `broken_open.stl` | drei offene Stellen — Reparatur, Rückfallkette |
| `broken_selfint.stl` | Selbstdurchdringung — robuste Boolesche Operation; einzelne Rückfallstufen werden zusätzlich gezielt erzwungen |
| `degenerate.stl` | Nadeln und Nullflächen — Eingangsstufe |
| `two_components.stl` | Würfel plus winziges Bruchstück — Kleinstteile werden gemeldet, nicht gelöscht |
| `oversized.stl` | größer als jeder Bauraum — Auto Split |
| `island_tower.stl` | Bereich ohne Verbindung nach unten — Inselerkennung (§22) |
| `clean_figure.stl` | organische Form, wasserdicht — Weg 4, Formen und Skelett |
| `generated_figure.stl` | organische Form, wie sie aus Säule B kommt — Reparaturkette |
| `dense_1m.stl` | ~1 Mio. Dreiecke — Leistungsmessung |
| `colored.3mf` | Materialgruppen — Attributerhalt |
| `assembly_fit.p3d` | zwei Teile mit Passung — Passungsprüfung |
| `example_v1.p3d` … | je eine Datei pro Altformat — Migrationen |

**Regeln für den Korpus:** ausschließlich selbst erzeugte Geometrie oder
eindeutig frei lizenzierte Modelle — der Korpus wird mit veröffentlicht.
Jede Datei hat eine Zeile in `tests/data/README.md`: was sie enthält, welche
Kennzahlen erwartet werden, welcher Test sie benutzt. **Diese Tabelle nennt,
wofür der Korpus da ist; die vollständige und gepflegte Liste ist jene
README** — aus demselben Grund wie bei der Paketkarte in §8. Neue Fehlerbilder
aus der Praxis werden als Datei aufgenommen, nicht als Sonderfall im Code.

---

## 35. Testbarkeit

| Art | Prüft |
|---|---|
| Kerntrennung | `core` ohne Qt importierbar |
| Registerkonsistenz | jede Op vollständig, Kürzel eindeutig, Startwert wo nötig |
| Sprachregelung | keine deutschen Stämme in Bezeichnern |
| Auswertung | zweimal ausgewertet = identisch; Objektzahländerung hält an |
| Geometrie | Kennzahlen je Operation gegen den Korpus |
| Rückfallkette | jede Stufe einmal erzwungen |
| Determinismus | gleicher Startwert → gleiches Ergebnis, alle vier Stellen |
| Bausteine | Vorschaubild und Merkmale sowie die Prüflogik für Parametergrenzen, Wandstärke und Selbstdurchdringung; vollständiger Bereichslauf bei Änderung des Bausteins oder seiner Grenzen von Hand, nicht in jedem Torlauf |
| Bausteinversion | geänderter Baustein wird beim Öffnen gemeldet |
| Schichtanalyse | Fläche und Volumen gegen analytisch bekannte Körper; `island_tower` erkannt |
| Parameter | Grammatik, Zyklen, Ablehnung von allem Übrigen |
| Passungen | Verletzung wird erkannt und gemeldet |
| Migrationen | alte Beispieldateien öffnen |
| Zuordnung | ID-Stabilität, Mehrdeutigkeitserkennung |
| Fehler | jede Ausnahme trägt mindestens einen Handlungsvorschlag |
| Barrierefreiheit | keine Bedeutung allein über Farbe |
| Oberflächengrenzen | höchstens neun Menüs, zwölf Zeilen je Menü, acht Umschalter, acht Felder auf der Vorderseite; eine sichtbare Handlung genau einmal, technisch gleichwertige Zwillinge und Varianten teilen ihren Einstieg |
| Leistung | Zielwerte §31, Regressionsschwelle 25 % |
| Lizenzen | installierte Abhängigkeiten gegen Freigabeliste |
| Hauptwege | die vier Wege aus §2.2 laufen als Ende-zu-Ende-Test |
| Anschluss | jede Zusage, die nur an **einer** Stelle eingelöst wird, wird an dieser Stelle geprüft — nicht „der Cache kann es", sondern „die Anwendung tut es" |
| Agenten-Suite | 39 Referenzanfragen — 21 zu Säule C (sechs seit der Agent-Vertiefung: nachsehen statt raten, Druckziel, Menüort), 18 zu Säule A |

Die Agenten-Suite misst zusätzlich: Wird ein vorhandener Baustein statt eigener
Geometrie benutzt? Werden Hauptabmessungen zu Parametern? Wird bei
Mehrdeutigkeit gefragt? Die Mechanik wird mit vorgeschriebenen Antworten in
`tests/` geprüft; die Verhaltensquote entsteht durch `tools/run_agent_suite.py`
gegen ein echtes, dokumentiertes Backend und Modell. Ein grüner Mechaniktest
ersetzt diesen Modelllauf nicht. Änderungen an Prompt, Regeln und
Werkzeugbeschreibung erhalten vergleichbare Vorher-/Nachher-Messungen (§39).

**Prüfbare Entscheidungen aus dem Zeichnen herauslösen.** Ein Test, der an
einer Offscreen-Wache umkehrt, prüft die dahinterliegende Darstellung nicht.
Reine Aussagen über Szene, Auswahl und Geometrie bekommen unabhängige Tests.
Attrappen prüfen anschließend die Übergabe an den Renderer; echte Picker,
Bildpuffer und native Lebensdauer brauchen zusätzlich einen echten Fensterlauf.
Fehlende Grafikfähigkeit ist dabei eine offene Abnahme, kein bestandener Bildtest.
Die Zahl bestandener Tests allein belegt keine ausgeführte Codefläche.

**Anschlussprüfungen messen die tatsächliche Nutzung.** Eine Fähigkeit, die
nur an einer Stelle eingelöst wird, wird dort geprüft. Drei Bauarten tragen:

- **Am echten Einstieg messen:** den Kundenweg fahren und die versprochene
  Wirkung dort beobachten, beispielsweise ein Projekt zweimal öffnen und
  die Wiederverwendung des Zwischenspeichers nachweisen.
- **Zwei Wege gegeneinander prüfen:** dieselbe Eingabe muss über zwei
  Einstiege dieselbe Aussage liefern; zwei isolierte Sollwerte würden einen
  fehlenden Anschluss unter Umständen verdecken.
- **Den einzigen Aufrufer prüfen:** eine angebotene Funktion allein beweist
  nicht, dass die Anwendung sie benutzt. Eine Quelltextsuche belegt auch
  einen Aufruf in einem toten Zweig und ersetzt diesen Test nicht.

Prüfer und Messsonden beobachten die versprochene Größe, nicht eine ähnliche:
Dateiinhalte statt bloßer Änderungszeit, den gesamten Cache statt nur seines
Speicheranteils. Instrumentiert wird die Referenz, die der Aufrufer benutzt;
eine an der Definition ersetzte Funktion erfasst kein bereits gebundenes
`from … import` im Aufrufer.

**Die Gegenfrage bleibt:** Was müsste kaputt sein, damit dieser Test rot wird,
und ist das genau der Fehler, vor dem er schützen soll? Gegenproben belegen
bei sicherheits- und korrektheitskritischen Zusagen, dass die Prüfung trifft.
Die historischen Fälle und Messreihen stehen im [Roadmap-Archiv](ROADMAP-ARCHIV.md).

---

## 36. Abhängigkeiten und Lizenzen

| Baustein | Lizenz | Folge |
|---|---|---|
| trimesh | MIT | unkritisch |
| manifold3d | Apache-2.0 | unkritisch, Kern der Bausteine |
| numpy, scipy | BSD | unkritisch; scipy trägt Skizzen-Solver und Zuordnung |
| shapely | BSD-3, bündelt GEOS (LGPL) | Polygonarbeit hinter Schnitt und Schichtanalyse |
| networkx | BSD-3 | Konturhierarchie des gedeckelten Schnitts — `rtree` ist am 24.08.2026 durch `app/core/geom/enclosure.py` (shapely-STRtree) ersetzt und steht auf der Sperrliste: libspatialindex korrumpierte den Heap |
| scikit-image | BSD-3 | Marching Cubes der Voxelstufe (§17.2) |
| lxml | BSD-3 | 3MF schreiben (§29) |
| vhacdx (V-HACD) | BSD-3 | konvexe Zerlegung fürs Auto Split |
| fast-simplification | MIT | dezimieren — der Ersatz für pymeshlab |
| svg.path | MIT | Zeichnungsimport; DXF liest trimesh selbst |
| pygfx, wgpu, rendercanvas | BSD-2-Clause; wgpu-native Apache-2.0 oder MIT | einziger Renderer der 3D-Ansicht; native Grafikbibliotheken werden mitgeliefert |
| VTK | BSD-3-Clause | ausschließlich kopflose Geometrie der Baustein-Bereichsprüfung, kein Renderer |
| PySide6 | LGPL | geschlossene Weitergabe möglich, wenn dynamisch gebunden. **PyQt wäre GPL — nicht verwenden.** |
| keyring | MIT | der Schlüssel des Nutzers im System-Schlüsselbund (§27) |
| cadquery-ocp-novtk (OpenCascade) | Anbindung Apache-2.0, Kern LGPL-2.1 mit Linking-Ausnahme | dynamisch gebundener B-Rep-Kern; keine zweite VTK-Kopie |
| build123d / CadQuery | Apache-2.0 | nicht eingesetzt; die Anwendung verwendet die OCP-Anbindung direkt |
| **pymeshlab** | **GPL** | **nicht verwenden** |
| open3d | MIT | **nicht verwendet** — Reparatur und Remeshing laufen über trimesh und manifold3d |
| CoACD | MIT | **geprüft und verworfen**, siehe unten |
| Slicer (Orca/Prusa/Cura) | GPL/AGPL | nur extern installiert aufrufen, nicht mitliefern |
| ComfyUI | GPL | extern, eigener Prozess — Weg 3 |
| Ollama | MIT | extern, eigener Prozess — der lokale Chat |
| Generative Modelle | uneinheitlich, teils regional eingeschränkt | einzeln prüfen |

**Die vollständige Aktenlage ist `app/core/knowledge/data/licences.toml`**, und
zwar aus einem Grund, den diese Tabelle nicht leisten kann: Dort steht auch,
was Solidon nur *aufruft* und was es in eine fremde Umgebung *installiert*. Ein
extern gestarteter Slicer taucht in keiner Prüfung der eigenen Laufzeit auf und
wäre sonst die einzige Abhängigkeit ohne Akte. Diese Tabelle nennt die
Entscheidungen, die Datei die Belege.

**Lizenz und Lieferbarkeit werden vor dem Einbau geprüft.** Eine neue native
Abhängigkeit braucht zulässige Lizenzbedingungen und installierbare Räder für
Windows, macOS und Linux in der Python-Version des Projekts. Ein eigener
Compilerweg ist eine gesonderte Architektur- und Auslieferungsentscheidung,
kein stiller Rückfall. Frühere Verfügbarkeitsprüfungen sind datierte Befunde;
sie sagen nicht, welche Räder ein Anbieter heute liefert.

**CoACD bleibt verworfen.** Am Auto-Split-Korpus lieferte V-HACD die bessere
Einschnürungsstelle; genau eingestelltes CoACD war langsamer, grobe
Einstellungen lieferten keine brauchbare Zerlegung. Ein erneuter Vergleich
braucht einen konkreten Anlass und neue Messwerte. Die historische Messung
steht im [Roadmap-Archiv](ROADMAP-ARCHIV.md).

**Die eigene Lizenz ist festgelegt:** `LICENSE` ist proprietär.
Bausteinbibliothek (`app/core/knowledge/parts/LICENSE`) und Referenzkorpus
(`tests/data/LICENSE`) stehen separat unter MIT. Die benannten Beispiele
tragen ihre zusätzliche Nutzungsfreigabe in `app/examples/LICENSE`.
Fremdlizenzen gehen den eigenen Bestimmungen für ihre Bestandteile vor.
Die Code-Lizenz und die kommerziellen Nutzungsbedingungen bleiben getrennte
Dokumente; fehlende Vertragsfreigaben stehen in der Roadmap.

**Lizenzhinweise** im Über-Dialog. Eine Prüfung vergleicht die installierten
Abhängigkeiten gegen die Freigabeliste.

---

## 37. Veröffentlichung und Auflagen

### 37.1 Name
**Entschieden: „Solidon3D".** Der volle Name steht auf Fenstertitel, Website,
Installer und Lizenzschlüssel; im Fließtext und in Docstrings heißt es kurz
„Solidon". Die zentrale Quelle ist `app/branding.py`.

Die Begründung und die verworfenen Namen stehen in
`konzepte/namensentscheidung-solidon.md`. Eine Produktentscheidung ist kein
Markenfreigabenachweis; der noch erforderliche rechtliche Abgleich bleibt in
[RM-093](ROADMAP.md#rm-093). Bei einer künftigen Namensänderung sind Domain,
Pakete, Supportadresse, Dateizuordnungen und Signierung gemeinsam abzugleichen;
die zentrale Konstante ersetzt diese externen Schritte nicht.

### 37.2 Auslieferung
- **Signierung und Plattformpakete.** Die CI baut Windows, Linux als
  AppImage und Flatpak sowie macOS für Apple Silicon und Intel. Der
  festgelegte Windows-Weg übergibt den gebundenen App-Baum an
  `tools/sign_release.py`; lokal signiert das Certum-Cloud-Zertifikat
  Anwendung und Setup-Datei. Apple benötigt Developer-ID-Signaturen und
  Notarisierung. Vorhandene CI-Schritte belegen weder den verfügbaren Zugang
  noch die erfolgreiche Signierung und Installation des Kundenpakets; diese
  Abnahmen bleiben [RM-001](ROADMAP.md#rm-001) und
  [RM-011](ROADMAP.md#rm-011).

  Die frühere pauschale Sperre für Microsofts Signierdienst ist überholt:
  Public-Trust-Zertifikate sind auch für Organisationen in der EU verfügbar;
  individuelle Entwickler bleiben auf USA/Kanada beschränkt. Das ist keine
  Bestätigung der konkreten Identitätszulassung und kein Wechsel vom
  beschlossenen Certum-Weg. Quelle:
  [Microsoft Artifact Signing](https://learn.microsoft.com/en-us/azure/artifact-signing/quickstart).
- **Automatische Bauläufe** über eine CI für alle Zielplattformen.
- **Ein Changelog, zwei Oberflächen.** Die Anwendung führt den mitgelieferten
  Versionsverlauf unter *Hilfe → Neuerungen* und lässt jede Fassung über ein
  Auswahlfeld einzeln lesen. Die Website zeigt denselben Verlauf in derselben
  Sprache und mit derselben Versionsauswahl. Gepflegt wird dafür nur
  `changelog/<sprache>.md`; der Auslieferungslauf erzeugt die Webfassungen
  automatisch daraus. Eine zweite Liste von Neuerungen gibt es nicht.
- **Update in der Anwendung, aber nur auf Knopfdruck.** Die Versionsdatei
  nennt neben der Version je Plattform Paketname, Adresse, Größe und
  SHA-256. Ist eine neuere da, sagt es ein sichtbarer Hinweis — keine Zeile,
  die die nächste Meldung überschreibt. Wer will, lädt das Paket aus der
  Anwendung heraus: mit Fortschritt, abbrechbar, und Solidon rechnet die
  Prüfsumme nach, bevor irgendetwas startet.

  Die Grenze liegt wie beim Fehlerbericht **nicht beim Vorgang, sondern beim
  Auslöser**: Es lädt nichts von allein, es ersetzt sich nichts im
  Hintergrund, und es startet nichts ohne einen Klick. Stimmt die Prüfsumme
  nicht, wird die Datei gelöscht und nichts ausgeführt. Das Paket kommt nur
  von demselben Rechnernamen wie die Versionsdatei; eine Adresse, die
  woandershin zeigt, wird nicht geladen.

  **Gegen wen das reicht, und gegen wen nicht.** Gegen einen Angreifer im Netz
  reicht es: Das Paket kommt nur von demselben Rechnernamen wie die
  Versionsdatei, über HTTPS, und wer dort etwas austauschen will, braucht ein
  Zertifikat für diesen Namen. Es reicht **nicht** gegen einen Angreifer, der
  den Server selbst hat. Der tauscht Paket und Prüfsumme gemeinsam — sie stehen
  in derselben Datei —, und in der Installation widerspricht nichts. Das ist
  eine engere Lücke als „die Prüfsumme trägt nicht", und deshalb die
  begründbarere: Sie ist mit einer Prüfsumme prinzipiell nicht zu schließen,
  egal wie sorgfältig man sie nachrechnet.

  **Deshalb wird die Versionsdatei unterschrieben, mit einem Schlüssel, der
  nicht auf dem Server liegt.** Solidon prüft die Unterschrift mit dem
  öffentlichen Teil aus der Installation, bevor es dem Inhalt glaubt; erst
  danach zählt der Rest — dieselbe Adresse, richtige Prüfsumme, Klick. Anhang I
  der Verordnung aus §37.3 verlangt ohnehin, dass Aktualisierungen sicher
  verteilt werden; dies ist die Stelle, an der das konkret wird.

  Zwei Auflagen gehören dazu, weil sie die Umsetzung prägen und sonst als
  Detail durchfallen. **Eine Versionsdatei ohne gültige Unterschrift ist
  Schweigen, kein Fehler** — dieselbe Behandlung wie eine ausgefallene
  Verbindung: kein Hinweis, kein Dialog. Ein Fehlerfenster beim Start wegen
  einer Datei, die der Nutzer nie sehen wollte, ist schlimmer als ein
  Aktualisierungshinweis, der einmal ausbleibt. Und **ein Schlüsselwechsel muss
  vorgesehen sein, bevor er nötig wird**: Eine ältere Installation kennt den
  neuen Schlüssel nicht und hört danach auf, Aktualisierungen zu sehen — also
  trägt die Installation mehr als einen zulässigen Schlüssel, und ein neuer
  wird eingeführt, solange der alte noch unterschreibt. Ein Schlüssel, der erst
  im Schadensfall gewechselt wird, ist einer, der nicht gewechselt werden
  kann.

  **Der Installationsweg folgt dem Paketformat.** Windows startet die
  geprüfte Setup-Datei, Flatpak spielt das geprüfte Bundle über den Host ein
  und startet die Anwendung wieder; macOS übergibt das geprüfte Paket an
  Apples Installer. AppImage und ausgepackte Archive bleiben beim Hinweis
  und dem Weg zur Download-Seite. Aus den Quellen wird kein Installer
  gestartet. Die tatsächliche Installation auf fremden Zielsystemen bleibt
  eine eigene Abnahme.
- **Übersetzbarkeit von Anfang an**; eine Prüfung schlägt bei unübersetzten
  Texten an.
- **Fehlerberichte und Rückmeldungen.** Keine Telemetrie. Ein Dialog stellt
  Fehlertext, Versionsangaben und auf Wunsch Bildschirmfoto, Protokoll und den
  Projektcontainer zusammen — mit Hinweis, dass Geometrie und Chat-Verlauf
  enthalten sind — und **sendet sie auf Knopfdruck** an den Supportkanal.
  Die Grenze zur verbotenen Telemetrie liegt nicht beim Versand, sondern beim
  Auslöser: Es geht nichts von allein, nichts ungesehen (Vorschau vor dem
  Senden) und nichts ohne Inhalt — ein geschriebener Satz oder, nach einem
  Absturz, der Stapelabzug, der sich selbst trägt. Der Weg
  ohne Netz bleibt derselbe Dialog — er legt den Bericht als Ordner ab.
- **Doku und Beispielprojekte**: genau die vier Hauptwege aus §2.2. Sie sind
  gleichzeitig Doku, Abnahmeprüfung und Startbildschirm-Inhalt.
- **Erwartungsmanagement.** Klar hinschreiben, was die Anwendung nicht ist —
  kein CAD-Ersatz, keine Passungen aus generierten Meshes.
- **Ein einziger Supportkanal.**

### 37.3 Regulatorische Auflagen

Dieser Abschnitt nennt die Produkt- und Betriebsanforderungen aus der
rechtlichen Einordnung. Konkrete Anwendbarkeit, Klassifizierung und
Vertragsgestaltung werden fachlich geprüft; Dokumente und technische
Schutzmaßnahmen allein sind keine Konformitätsfreigabe. Offene Entscheidungen
stehen in [RM-093](ROADMAP.md#rm-093).

**Cyberresilienz-Verordnung (CRA, (EU) 2024/2847).** Die Arbeitsgrundlage ist,
Solidon als kommerzielles Produkt mit digitalen Elementen einzuordnen. Die
Ausnahme für nicht kommerzielle freie und quelloffene Software trägt die
proprietäre Anwendung nicht. Die Einstufung des konkreten Produktumfangs und
das anwendbare Konformitätsverfahren werden dokumentiert; eine gewöhnliche
3D-Konstruktionsanwendung ist nicht allein deshalb ein Produkt der Anhänge III
oder IV.

| ab | Anforderung |
|---|---|
| **11.09.2026** | Art. 14: aktiv ausgenutzte Schwachstellen und schwere Sicherheitsvorfälle melden; Frühwarnung binnen 24 Stunden ab Kenntnis, Hauptmeldung binnen 72 Stunden, anschließend der jeweils vorgeschriebene Abschlussbericht |
| **11.12.2027** | Allgemeine CRA-Pflichten, insbesondere Anhang I, Konformitätsbewertung, CE-Kennzeichnung, EU-Konformitätserklärung, technische Dokumentation, Stückliste, Schwachstellenverfahren und Sicherheitsunterstützung |

Bei einer aktiv ausgenutzten Schwachstelle folgt der Abschluss spätestens
14 Tage nach Verfügbarkeit einer Korrektur oder Risikominderung, beim schweren
Vorfall binnen eines Monats nach der 72-Stunden-Meldung. Gemeldet wird einmal
über die Single Reporting Platform an das zuständige CSIRT; ENISA erhält die
Information nach dem gesetzlichen Verfahren. Der betriebliche Ablauf steht
in `SECURITY-INCIDENT.md`; funktionsfähige Zugänge, Vertretung, Alarmierung und
Probelauf bleiben [RM-091](ROADMAP.md#rm-091). Die früheren „binnen 24 Stunden"
umfassen nur die erste Meldestufe. Quellen:
[EU-Kommission zu den Meldepflichten](https://digital-strategy.ec.europa.eu/de/policies/cra-reporting),
[ENISA Single Reporting Platform](https://www.enisa.europa.eu/topics/product-security/single-reporting-platform-srp).

Für die weitere CRA-Vorbereitung gelten diese Liefergegenstände:

1. **Stückliste des ausgelieferten Produkts.** `tools/make_sbom.py` erzeugt
   CycloneDX 1.6 aus dem tatsächlichen PyInstaller-Laufzeitbaum;
   `packaging/solidon3d.spec` legt `Solidon3D.cdx.json` ins Paket. Erfasste
   Python- und native Bestandteile, Paketbezug und Belege werden je
   Zielartefakt geprüft. `constraints.txt` allein ist keine Stückliste des
   Kundenpakets; die durchgesetzte Releaseakte bleibt
   [RM-115](ROADMAP.md#rm-115).
2. **Schwachstellenverfahren.** `SECURITY.md` benennt den Meldekanal und die
   zugesagte Antwortzeit, `SECURITY-INCIDENT.md` die Bearbeitung und
   gesetzlichen Meldepfade. Die öffentliche Sicherheitsseite muss damit
   übereinstimmen; Bereitschaft wird praktisch nachgewiesen.
3. **Unterstützungsdauer.** Für Solidon 1.x ist mindestens der
   31. Oktober 2031 zugesagt. Erwartete Nutzungsdauer und gesetzliche
   Mindestunterstützung werden vor jeder späteren Bereitstellung erneut
   geprüft; der feste Termin ersetzt diese Prüfung nicht. Art. 13 Abs. 8
   verlangt grundsätzlich mindestens fünf Jahre, bei kürzer erwarteter
   Nutzung deren Dauer. Eine längere erwartete Nutzung kann längeren Support
   verlangen. Quelle:
   [CRA, insbesondere Art. 13](https://eur-lex.europa.eu/eli/reg/2024/2847/oj/deu).
4. **Konformitätsakte.** Technische Dokumentation, Risikoanalyse,
   nachgewiesene Anforderungen des Anhangs I, das richtige
   Konformitätsverfahren, EU-Konformitätserklärung und CE-Kennzeichnung
   werden zum jeweils gesetzlich erforderlichen Zeitpunkt abgeschlossen.
   Kleinunternehmens-Erleichterungen ersetzen die materiellen Anforderungen
   nicht. Diese Akte ist nicht bereits durch Lizenzliste und SBOM erledigt.

**Barrierefreiheitsstärkungsgesetz (BFSG).** Die Desktop-Anwendung gehört nach
dem beschriebenen Produktumfang nicht zur Produktliste in §1 Abs. 2. Der
Verkauf über die Website ist gesondert als elektronischer Geschäftsverkehr
zu beurteilen. Für Dienstleistungen besteht die Ausnahme nach §3 Abs. 3,
solange RS Digital Kleinstunternehmen gemäß §2 Nr. 17 ist: weniger als zehn
Beschäftigte und höchstens zwei Millionen Euro Jahresumsatz oder Bilanzsumme.
Diese tatsächlichen Voraussetzungen sind bei einer Änderung des Geschäfts
neu zu prüfen. Die Anforderungen aus §19 bleiben unabhängig davon verbindliche
Produktqualität. Quellen:
[BFSG §1](https://www.gesetze-im-internet.de/bfsg/__1.html),
[BFSG §2](https://www.gesetze-im-internet.de/bfsg/__2.html),
[BFSG §3](https://www.gesetze-im-internet.de/bfsg/__3.html).

**KI-Verordnung.** Der Chat macht vor der Interaktion deutlich, dass ein
KI-System antwortet. Ob diese Kennzeichnung die konkrete Transparenzpflicht
nach Art. 50 Abs. 1 erfüllt, wird am tatsächlich angebotenen Einstieg geprüft.
Die Rolle als Anbieter oder Betreiber des integrierten KI-Systems ist von der
Rolle des Anbieters des zugrunde liegenden Modells zu unterscheiden. Die
Nutzung eines fremden Modells schließt eigene Systempflichten nicht pauschal
aus. Weitere einschlägige Transparenzpflichten, insbesondere für erzeugte
Inhalte nach Art. 50 Abs. 2, bleiben Teil der fachlichen Rollen- und
Produktprüfung in [RM-093](ROADMAP.md#rm-093). Die Ziele aus §5 und §27 gelten
weiter: Empfänger einer Eingabe erkennbar machen und externe Übermittlung nur
über das eingerichtete Backend. Quelle:
[KI-Verordnung, Art. 3 und 50](https://eur-lex.europa.eu/legal-content/DE/TXT/?uri=CELEX:32024R1689).

---

## 38. Desktop-Spezifika

- **Erstinbetriebnahme** folgt §2.3. Zusatzprogramme und Chat werden
  unabhängig von der verpflichtungsfreien Grundauswahl geprüft und optional
  eingerichtet; ein fehlendes Zusatzprogramm blockiert den Start nicht.
- **Nebenläufigkeit.** Längere Berechnungen und Ein-/Ausgabe laufen in der
  Oberfläche außerhalb des Qt-Hauptthreads, mit Fortschritt und Abbruch nach
  §2.8 und §15.6. Der Kern bleibt synchron aufrufbar; die Kommandozeile
  benötigt dafür keinen zusätzlichen Worker.
- **Absturzwiederherstellung.** Benannte eigene Projekte erhalten eine
  Autosave-Datei neben dem Projekt. Noch ungespeicherte Projekte und
  mitgelieferte Beispiele werden im Wiederherstellungsordner des Nutzers
  gesichert. Ungespeicherte Dokumente haben je eine eigene Kennung; eine
  andere laufende Sitzung darf ihre Sicherung nicht als verwaist anbieten.
  Beim nächsten Öffnen werden wiederherstellbare Stände angeboten.
- **Speicher und Cache.** Ein begrenzter Speichercache und darunter ein
  Plattencache über den vollständigen Auswertungsschlüssel beschleunigen
  denselben Kern in Oberfläche und Kommandozeile. Der Ergebnis-Cache hat
  einen eigenen, nach Anwendungsfassung getrennten Ordner. Sein Budget und
  seine Bereinigung erfassen ausschließlich Ergebnisdaten, keine
  Aktualisierungspakete, Werkzeug-Arbeitsordner oder Oberflächenvorlagen.

  Der Schlüssel berücksichtigt Operation, aufgelöste Parameter, Eingänge,
  relevantes Profil, Qualitätsstufe und Startwert sowie alle weiteren
  ergebniswirksamen Abhängigkeiten. Quellen werden durch ihren Inhalt
  unterschieden, nicht durch projektlokale Namen wie `src_1`. Auch der Stand
  eigener Bausteine muss eine Änderung des berechneten Ergebnisses vom alten
  Cache trennen. Ein Anwendungswechsel verwendet einen neuen Ergebnisordner
  und bereinigt ausschließlich die Ergebnisordner älterer Fassungen.

  Eine eingebettete Quelle erhält ihre Inhaltsprüfsumme beim Anlegen. Eine
  verknüpfte externe Quelle darf nur solange wiederverwendet werden, wie ihre
  Aktualität geprüft ist; fehlt die Prüfsumme, wird der Inhalt gelesen und
  gehasht. Auf Platte gelangen nur Ergebnisse, die vollständig aus dem
  Dokument reproduzierbar sind. Nicht gespeicherte Rückfrageantworten
  schließen das Ergebnis vom Plattencache aus (§15.7).

  Der Plattencache ist keine Betriebsvoraussetzung. Kann sein Ordner nicht
  verwendet werden, arbeitet die Sitzung mit dem Speichercache weiter und
  protokolliert den Grund ohne blockierenden Dialog. Anschluss, Trennung
  verschiedener Projekte und Entwertung nach relevanten Änderungen werden
  am tatsächlichen Anwendungsweg geprüft; historische Laufzeiten sind keine
  allgemeinen Leistungszusagen.
- **Zugangsdaten** im System-Schlüsselbund.
- **Profile**: Bauraum, Düse, Schichthöhe, Materialtoleranzen — nie fest im
  Code. **Ein Startsatz gängiger Druckerprofile wird mitgeliefert**, damit
  beim ersten Start niemand Bauraummaße abtippt; eigene Profile werden davon
  abgeleitet. Der Startsatz ist eine Datentabelle wie die Normteile (§24.2)
  und wird genauso gepflegt.
- **Paketierung.** PyInstaller bündelt die Anwendung. ComfyUI, Ollama und
  Slicer werden separat eingerichtet. Verfügbarkeit wird ohne Blockade des
  Starts geprüft; fehlende optionale Programme werden an ihrer Funktion
  verständlich erklärt und sperren keine unabhängigen Arbeitswege.

---

## 39. Die Regelsammlung

Die verbindlichen Regeltexte leben in
`app/core/knowledge/data/rules.toml`, geladen durch
`app/core/knowledge/rules.py`. Der Bauplan hält Pflege und Priorität fest;
eine zweite, von der Datei abweichende Regelkopie wird hier nicht geführt.
Die Sammlung hat Version und Änderungsverlauf. Jede inhaltliche Änderung
trägt Datum, Anlass und vergleichbare Suite-Ergebnisse vorher und nachher.
Verschlechtert sich die Quote, wird die Regel korrigiert oder zurückgenommen.
Fehlende Modellmessungen bleiben als offene Abnahme erkennbar; eine erhöhte
Versionsnummer ersetzt sie nicht.

Der Systemprompt nennt die Regelversion; jede Agententransaktion hält sie
zusammen mit Modell, Prompt-Version und Temperatur fest (§26.4). Übersetzungen
für das Handbuch ändern keine Regel; inhaltliche Änderungen tun es und ziehen
alle betroffenen Darstellungen nach.

Die Sammlung deckt Mindestwandstärke, Fasen statt Überhängen, kalibrierte
Passungstoleranzen, Projektparameter, Boolesche Überlappung,
Bohrungskompensation, Elefantenfuß sowie die beiden Vorgehensregeln
„Bausteine vor Primitiven" und „Fragen vor Raten" ab. Werte, Geltungsbereiche
und Wortlaut stehen in der einen Quelldatei. Sie müssen den Zahlenregeln und
den tatsächlichen Druckverfahren entsprechen; ein widersprüchlicher Regeltext
ist ein offener Fund, keine Ausnahme vom Bauplan.

Was sich als Baustein fassen lässt, wandert aus der Sammlung in die Bibliothek.
Eine im Werkzeug durchgesetzte Regel ist verlässlicher als eine nur
beschriebene. Neue Druckverfahren brauchen ausdrücklich passende
Geltungsbereiche; die beschlossene FDM-/Resin-Trennung steht in
[RM-071](ROADMAP.md#rm-071). Noch fehlende Verhaltensmessungen stehen in
[RM-014](ROADMAP.md#rm-014), [RM-016](ROADMAP.md#rm-016) und
[RM-069](ROADMAP.md#rm-069).

---


## 40. Phasen mit Abnahmekriterien

Hier stehen Umfang, Zielmodule und Abnahmekriterien der Phasen. Der erreichte
Stand und die verbliebenen Aufgaben stehen in `ROADMAP.md`; diese Liste ist
keine zweite Fortschrittstabelle. Ein gebautes Modul, ein geskripteter
Backend-Test oder ein vorhandener Paketjob ersetzen keine ausdrücklich
geforderte Modell-, Feld-, Signier- oder Rechtsabnahme.

### P0 — Skelett
*Module:* `core/types`, `core/errors`, `core/units`, `core/registry`,
`core/scene`, `core/ingest`, `core/knowledge/profiles`, `cli`, `ui`
(Grundfenster, Viewport, Objektbaum, Parameterleiste, Verlauf), `tests/data`

*Fertig, wenn:* `core` ohne Qt importierbar · Sprachregelungstest grün · zwei
Ops im Register, sichtbar in Menü, Palette, Kontextmenü, CLI und Tool-Schema ·
Projekt speichern und laden erhält den Stack bitgleich · zweimalige Auswertung
liefert identische Geometrie · Undo/Redo über zehn Transaktionen · Import in
mm, Zoll und cm mit Einheitenrückfrage · Parameteränderung rechnet nur den
betroffenen Zweig · Ausdrucksauswerter lehnt alles außerhalb der Grammatik ab ·
Startbildschirm mit Ablagefeld · Startsatz Druckerprofile vorhanden und
auswählbar · Lizenzprüfung grün.

### P1 — Sehen und Messen
*Module:* `ui/viewport` (Modi, Schnittebene, Messen, Gizmo, Snapping),
`ui/theme`

*Fertig, wenn:* Schnittfläche erscheint geschlossen (Bildvergleich) ·
gemessener Durchmesser weicht unter 0,01 mm ab · jede Gizmo-Manipulation
erzeugt genau eine Op · keine Bedeutung allein über Farbe · Navigation in allen
angebotenen Schemata · Leistungsziele Viewport erreicht.

### P2 — Operationen manuell
*Module:* `core/geom` (Reparatur, Transformation, Boolesch mit Rückfallkette,
Bohrungen, Schneiden, Anordnen), `core/export`

Die druckoptimale Orientierung bleibt hier eine Heuristik über
Flächennormalen; sie wird in P3 durch die Schichtanalyse ersetzt.

*Fertig, wenn:* jede Op hat einen Geometrietest gegen den Korpus · die
Rückfallkette löst `broken_open` und `broken_selfint` vollständig · verwendete
Stufe und Startwert stehen in der Op · gleicher Startwert liefert gleiches
Ergebnis · 3MF-Export öffnet im Slicer mit korrekten Objektnamen · **Weg 1 aus
§2.2 läuft als Ende-zu-Ende-Test** · Zielwerte §31 erreicht.

### P3 — Wahrnehmung und Schichtanalyse
*Module:* `core/perceive`, `core/slice`, `ui/overlay`, `ui/panels`
(Prüfbericht), `ui/analysis_bar` (Schichtansicht)

*Fertig, wenn:* `plate_holes` vollständig erkannt · IDs bleiben über zehn Ops
stabil · `plate_holes_twin` wird als mehrdeutig gemeldet statt geraten · Klick
liefert die korrekte Feature-ID und das passende Kontextmenü · Klick auf eine
Warnung schaltet die Karte ein und fährt die Kamera hin · verletzte Passung
erscheint im Bericht · **Schichtanalyse**: Fläche und Stützvolumen stimmen bei
analytisch bekannten Körpern auf 1 % · `island_tower.stl` wird erkannt ·
Orientierungssuche über 200 Kandidaten liefert weniger Stützvolumen als die
Heuristik aus P2 · Schichtenvorschau scrubbt flüssig · Zielwerte §31 für die
Schichtanalyse erreicht.

### P4 — Agent auf Säule C
*Module:* `core/agent`, `core/backends/llm`, `ui/chat`

*Fertig, wenn:* Agenten-Suite zu Säule C besteht die Zielquote · bei
mehrdeutigen Anfragen wird `ask_user` benutzt · ein Vorschlag ist genau eine
Transaktion und wird mit einem Undo vollständig zurückgenommen · nach einem
Undo verweist kein Kontext mehr auf die verworfene Transaktion · jede Op ist
schemagültig, bevor gerechnet wird.

### P5 — Bausteinbibliothek
*Module:* `core/knowledge/parts`, `core/knowledge/standards`, `ui/catalog`

*Fertig, wenn:* **jeder** Baustein der Bibliothek über seinen Parameterbereich
wasserdicht und wandstärkenkonform — die Erstbestückung aus §24.1 sind
dreizehn, es sind inzwischen mehr, und eine Zahl in einem Abnahmekriterium
altert schneller als die Bibliothek · Features als Provenienz-IDs im Steckbrief · Vorschaubilder
automatisch gerendert · `to_scad()` erzeugt gültigen Quelltext · kein Kernpfad
braucht ein externes Programm · `parts_version` in der Projektdatei,
geänderter Baustein wird beim Öffnen namentlich gemeldet · eigene Bausteine
aus dem Nutzerordner werden geladen und reisen nachweislich nicht mit der
Projektdatei.

### P6 — Säule A
*Fertig, wenn:* Agenten-Suite zu Säule A besteht · Bausteine werden messbar vor
eigener Geometrie bevorzugt · Hauptabmessungen landen messbar als Parameter ·
**Weg 2 aus §2.2 läuft als Ende-zu-Ende-Test** · es gibt nachweislich keinen
Weg, auf dem Quelltext aus einer Projektdatei oder aus dem LLM ausgeführt
wird (§32).

### P7 — Slicer-Rückkopplung und Kalibrierung
*Fertig, wenn:* die G-Code-Gegenprobe weicht auf dem Korpus um weniger als
15 % von der internen Schätzung ab, größere Abweichung erscheint als Befund ·
Herkunft jeder Kennzahl im Bericht ausgewiesen (intern oder G-Code) ·
geänderte Profilwerte schlagen auf bestehende Projekte durch, ohne sie zu
ändern · Suche bei gleichem Startwert reproduzierbar.

### P8 — Erste Veröffentlichung
*Fertig, wenn:* Name entschieden · Installationsdateien aus der CI für alle
Zielplattformen · alle Texte übersetzt · die Beispielprojekte der Hauptwege
(§2.2) öffnen und
rechnen fehlerfrei · Erstinbetriebnahme führt bis zum ersten Import ·
Lizenzhinweise vollständig.

Bewusst **vor** Säule B: Der Editor mit Agent ist für sich vollständig, und
frühe Rückmeldungen sind mehr wert als ein weiteres Feature.

### P9 — Säule B und Farbe
*Fertig, wenn:* generiertes Mesh durchläuft die Reparaturkette zu einem
wasserdichten Ergebnis · Filamentzuweisung überlebt Boolesche Ops einschließlich
Stufe „voxel" · Quantisierung bei gleichem Startwert reproduzierbar · `3MF`
öffnet im Slicer mit korrekten Farbgruppen · **Weg 3 aus §2.2 als
Ende-zu-Ende-Test**.

### P10 — Auto Split mit Verstiftung
*Fertig, wenn:* jedes Teil einzeln wasserdicht · Passungspaare automatisch
angelegt und geprüft · `oversized.stl` wird ohne Eingriff druckbar zerlegt.

### P11 — Gehosteter Generierungs-Backend, falls Nachfrage besteht.

Zurückgestellt. Erst Nachfrage und eine ausdrückliche Produktfreigabe eröffnen
die Phase; vor dem Bau werden ihre Abnahmekriterien entlang §27 festgelegt.

### P12 — B-Rep-Kern
*Fertig, wenn:* Verrundung an einer Referenzkante geometrisch exakt · STEP
rundreisefähig · Kennzeichnung Mesh/B-Rep korrekt.

### P13 — Skizzen und tiefere Konstruktion
*Module:* `core/sketch` (Datenmodell, Solver), `core/brep`
(Formgebungs-Ops), `ui/sketch_editor` (Editor)

*Fertig, wenn:* der Solver bei gleichem Modell die gleiche Lösung liefert ·
widersprüchliche Bedingungen nennen das kollidierende Paar statt
„fehlgeschlagen" · ein Skizzenmaß rechnet mit einem Projektparameter und die
Änderung schlägt durch · die Grundformen sind über Dialog, CLI und Agent ohne
Grafikeditor benutzbar · der Agent erzeugt nachweislich keine rohen
Punktlisten · ein Referenzteil (Gehäuse mit passendem Deckel) entsteht von
leerer Szene bis Export ohne Fremd-CAD, als Ende-zu-Ende-Test · Formschräge,
exakte Schale, Sweep, Loft und exaktes Gewinde mit Geometrietest gegen den
Korpus · Skizzen-Solver im Leistungsziel (§31) · ohne `brep` bleibt alles
andere benutzbar.

Skizzen gehören zum Veröffentlichungsumfang. Die Abnahme dieser Phase ist
Voraussetzung für die Zusage, tiefere Konstruktion ohne Fremd-CAD zu tragen;
Veröffentlichungsabnahmen aus P8 werden dadurch nicht ersetzt.

### P14 — Die Oberfläche einlösen
*Module:* `ui` durchgehend, `scene/history`, `agent/apply`

Parameter, Passungen, Drucker und Material gehören ebenso zur
Dokumenttransaktion wie Operationen. Undo, Änderungsmarkierung und Speichern
müssen über denselben Kundenweg alle Dokumentänderungen erfassen.

*Fertig, wenn:* jede Änderung am Dokument geht durch eine Transaktion, auch
wenn sie keine Operation enthält · ein Strg+Z nach einem angenommenen Vorschlag
nimmt dessen Parameter und Passungen mit zurück · jede ungespeicherte Änderung
steht im Titel · die Tests nehmen den Weg, den ein Mensch nimmt, und nicht den
kurzen daneben — ein Test, der die Rücknahme direkt aufruft statt über die
Oberfläche, deckt genau diesen Fund zu.

### P15 — Konstruieren und zeigen
*Module:* `ui/sketch_editor`, `ui/viewport`, `geom/texture_ops`, `geom/lattice`,
`core/scene/ops` (Anordnung), `ui/remote_server`, `agent/remote`

Konstruktionswerkzeuge, Bediensprache und Darstellung halten die
Oberflächengrenzen: höchstens neun Menüs, zwölf Zeilen je Menü, acht
Umschalter und acht Felder auf der Vorderseite eines Dialogs. Eine sichtbare
Handlung steht genau einmal; technisch gleichwertige Zwillinge und Varianten
teilen ihren Einstieg. Begründet abgelehnter Umfang wird im Konzept erhalten.

*Fertig, wenn:* die Obergrenzen sind Tests und grün · der Skizzenmodus arbeitet
ohne Dialog auf einer angeklickten Fläche · Texturen sind echte Geometrie, flach
und umlaufend · die Fernsteuerung nach §26.6 läuft mit allen fünf Auflagen · was
begründet nicht gebaut wurde, steht mit seinem Grund im Konzept und nicht als
Lücke da.

### P16 — Organische Modellierung
*Module:* `geom/sculpt`, `geom/pose`, `geom/blend`, `ui/sculpt_bar`,
`ui/pose_bar`, `ui/viewport`

Weg 4 aus §2.2 umfasst Figuren und Posing. Regel 2 verlangt keine einzelne
Operation je Nutzergeste: Der Editor sammelt reproduzierbare Parameter und
zeigt währenddessen eine Vorschau; den Dokumentzustand erzeugt erst die
Auswertung. Geeignete Striche werden gemeinsam über einen räumlichen Index
berechnet. Werkzeuge, deren Reihenfolge das Ergebnis verändert, rechnen in
Etappen; ihre Semantik wird nicht zugunsten einer Laufzeitmarke vertauscht.

*Fertig, wenn:* ein Editor sammelt beliebig viele Gesten in einen Parameterwert,
und das Ergebnis entsteht erst bei der Auswertung · fünftausend Striche bleiben
im Leistungsziel · **Weg 4 aus §2.2 läuft als Ende-zu-Ende-Test** · das
Beispielprojekt liegt bei und das Handbuch hat sein Kapitel.

---

## 41. Ausbaustufen

Die folgenden Erweiterungen sind mögliche Ausbaustufen, keine bereits
beauftragten Aufgaben. Eine Umsetzung beginnt erst nach einer ausdrücklichen
Umfangsentscheidung und Aufnahme in `ROADMAP.md`.

**Vorlagenbibliothek.** Verwaltung von wiederverwendbaren Projekten mit
Parametern, Bausteinen und Operationen; der vorhandene Projekt- und
Beispielweg bleibt die Grundlage (§13, §37).

**Fallbibliothek.** Erfolgreiche Paare aus Anfrage und Transaktion lokal
speichern und bei ähnlichen Anfragen mitgeben. Anfragen der Agenten-Testsuite
dürfen nie in diese Sammlung gelangen; Lernbestand und Abnahme bleiben
getrennt.

**Stapelverarbeitung.** Mehrere Dateien über den vorhandenen
Kommandozeilen-Einstieg verarbeiten. Die Einzelbefehle benutzen bereits
denselben Kern wie die Oberfläche; ein zusätzlicher Stapelablauf braucht
einen eigenen Umfang und nachvollziehbare Ergebnisse je Datei.

**Modellvergleich.** Zwei unabhängige Modellfassungen überlagern und ihre
Unterschiede darstellen. Die vorhandene Vorher-/Nachher-Ansicht einer
Transaktion nach §18.7 bleibt davon getrennt.

**Druckerhistorie.** Druckaufträge mit benutzten Einstellungen und
Ergebnisnotiz erfassen. Eine Nutzung für die Regelsammlung benötigt eine
eigene Entscheidung und die Abnahme nach deren Änderungsvertrag.

**Keine Ausbaustufen sind** Web-Anwendung im Browser, Mehrbenutzerbetrieb,
Cloud-Ablage von Projekten, Plugin-System, Telemetrie, Verzweigungen im
Op-Stack und ein eigener G-Code-Slicer. Parametervarianten nach §28.3
erzeugen keine verzweigte Verlaufshistorie.

Eigene Bausteine nach §24.5 erweitern die Bibliothek, nicht die Anwendung.
Ausführbarer Python-Code bleibt lokal und reist nie in einer Projektdatei.
Ein Bausteinrezept darf als Daten aus registrierten Operationen und Werten
mitreisen; daraus entsteht kein Weg zur Ausführung fremden Quelltexts.

---

## 42. Grenzen, die bleiben

- Generierte Meshes liefern keine verlässlichen Passmaße. Maßgebundene
  Flächen und Passungen entstehen danach durch geprüfte Operationen und
  Projektparameter.
- Die Tragfähigkeit hängt von Material, Geometrie, Orientierung und
  Druckverfahren ab. Profilbezogene Mindestwandstärken sind Prüfgrenzen,
  keine Festigkeitsgarantie.
- Ein importiertes Mesh hat keine Konstruktionshistorie. Merkmalserkennung
  rekonstruiert erkennbare Geometrie, nicht die ursprünglichen
  Konstruktionsschritte. STEP liefert bearbeitbare Flächen und Kanten,
  ebenfalls keine ursprüngliche parametrische Historie (§30).
- Rückfallstufe „voxel" rettet die Operation, kostet aber Genauigkeit
- Reproduzierbarkeit gilt nur bei gleichen Bibliotheksversionen
- Farbquantisierung aus Texturen bleibt gröber als das Rendering
- Verrundungen und Fasen an exakten Kanten benötigen einen B-Rep-Körper.
  Erkannte Merkmale eines Meshes machen es nicht automatisch zu einer
  bearbeitbaren B-Rep-Konstruktion; eine Flächenrückgewinnung ist ein eigener
  möglicher Ausbau (§30).
- Baugruppen mit echten Funktionstoleranzen bleiben Handarbeit; der Agent
  liefert den Entwurf, nicht das Endergebnis
- Die Zielwerte in §31 gelten mit dem übersetzten Schichtkern; ohne ihn ist die
  Schichtanalyse an der Decke des Interpreters, und das ist an drei Verfahren
  gemessen und nicht geschätzt
- Die Wahrnehmung erkennt nach §21.1 unter anderem Ebenen, Zylinder, Kegel,
  Kugeln, Tori und geeignete Torusstücke. Eine Form wird nur bei ausreichend
  belegter Einpassung veröffentlicht; ein zu kleiner oder uneindeutiger
  Ausschnitt bleibt ein Cluster. Die Krümmungskarte zeigt vorhandene
  Merkmalsradien und kennzeichnet die davon getrennte Schätzung aus
  Nachbarflächen (§18.4).

---

## 43. Nächster Schritt

Die aktuelle Reihenfolge, Fristen und Abnahmereste stehen ausschließlich in
`ROADMAP.md`. Dieser Bauplan legt die Produktverträge und die Phasenabnahme
aus §40 fest; er führt keinen zweiten Aufgabenbestand.

Bei der Priorisierung kommen verbindliche externe Fristen und bekannte
Kundenfehler vor neuen Ausbaustufen. Eine gebaute Funktion gilt erst nach
ihrer vereinbarten Abnahme als abgeschlossen; die Nachweise und verbleibenden
Plattform- oder Feldprüfungen werden am zugehörigen Roadmap-Punkt geführt.

`AGENTS.md` und die einschlägigen Skills bestimmen den Arbeits- und Prüfweg.

---
