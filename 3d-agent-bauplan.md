# Solidon — Bauplan v11

Desktop-Anwendung zum **Konstruieren, Generieren und Bearbeiten** druckbarer
3D-Modelle. Non-destruktiver Operationsstack über einer Szene mit mehreren
Objekten, vollwertiger Viewport, Bausteinbibliothek, Rückkopplung aus Slicer
und Drucker. Veröffentlichung als Download; online nur Website und optionaler
Generierungs-Backend.

Spezifikation zur Abarbeitung durch einen Programmier-Agenten.
Begleitdateien: `AGENTS.md` (Repository-Regeln, immer lesen) und `ROADMAP.md`
(Arbeitsliste je Phase).

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

## 0. Änderungen gegenüber v10

Eine Durchsicht, keine Erweiterung: Es kommt keine Säule dazu und nichts von
der Nicht-bauen-Liste zurück. Was dazukommt, sind Stellen, an denen der Plan
hinter dem Code zurückhing, fünf Entscheidungen, auf die das Register von
`ROADMAP.md` ausdrücklich gewartet hat, und ein Kapitel, das gefehlt hat.

**Neu: §37.3 Regulatorische Auflagen** — der teuerste Fund. Die Verordnung
über Cyberresilienz gilt für jedes kommerziell in Verkehr gebrachte Erzeugnis
mit digitalen Elementen, und Solidon ist eines. Ab dem **11.09.2026** — drei
Wochen nach dieser Durchsicht — sind aktiv ausgenutzte Schwachstellen binnen
24 Stunden zu melden; ab dem 11.12.2027 kommen CE-Zeichen,
Konformitätserklärung, Stückliste und Schwachstellenverfahren dazu. Es stand
in keiner Unterlage. Umgekehrt gilt das Barrierefreiheitsstärkungsgesetz für
Solidon **nicht** — bei beiden ist die naheliegende Vermutung die falsche, und
§37.3 begründet beides.

**Fünf Entscheidungen, die das Register vom Bauplan verlangt hat.** §15.7 sagt,
wohin die Antwort auf eine Rückfrage gehört: in die Parameter der fragenden
Operation, weil §15.1 keine zweite Möglichkeit offenlässt — 99 modale Fenster
für 7 Entscheidungen waren die Rechnung dafür, dass es niemand hingeschrieben
hat. §31 sagt, dass der übersetzte Schichtkern mitgeliefert wird, was ein roter
Leistungstest bedeutet und welche der beiden Reparaturen die
Regressionsschwelle bekommt. §21.2 sagt, was ein angeklicktes Gewinde anbietet
— und beantwortet damit nicht die Frage nach dem Gewinde, sondern die nach
jedem erzeugten Merkmal. §29 sagt, dass 52 Teile auf sieben Platten zu viel
sind und woran es liegt: nicht an der Sortierung, an den Zeilen. §36
beantwortet das „prüfen", das dort bei CoACD stand, mit der Messung, die es
längst gibt.

Vier davon fielen leichter als erwartet, und aus demselben Grund: **Die Antwort
stand schon im Bauplan, nur nicht an der Stelle, an der jemand sie sucht.**
§15.1 lässt für eine Rückfrageantwort nichts anderes zu; die Provenienz aus
§21.2 trägt das Kontextmenü, seit es sie gibt; das geteilte Tor macht die eine
der beiden Regressionsreparaturen unbrauchbar; die Messung zu CoACD lag seit
acht Tagen vor. Eine Entscheidung, die aus zwei vorhandenen Sätzen folgt, ist
keine Entscheidung — sie ist eine Lücke im Register.

**Zwei Verfahren, für die die Recherche etwas Besseres gefunden hat.** Die
Orientierungssuche zieht ihre Kandidaten aus den Flächen der konvexen Hülle
statt aus Zufallsrichtungen (§28.2) — weniger Kandidaten, bessere Ergebnisse,
und eine der vier gewürfelten Stellen aus §11.3 fällt dabei weg. Die
Aktualisierung bekommt eine Unterschrift statt einer Prüfsumme, die auf
demselben Server liegt wie das Paket, das sie sichern soll (§37.2).

**Zwei Stellen, an denen der Code strenger war als der Plan.** Die
Fernsteuerung prüft die Herkunft jeder Anfrage, nicht nur die Bindung an
`127.0.0.1` (§26.6, fünfte Auflage); der Kontext des Agenten steht in einer
Reihenfolge, die das Zwischenspeichern beim Modell überhaupt erst greifen
lässt (§26.1). Beides war gebaut und nirgends gefordert. Ein Test, der
schärfer ist als der Bauplan, sieht wie Sicherheit aus, bis jemand den Bauplan
für die Wahrheit nimmt und die Prüfung entfernt.

**Und §40 kennt jetzt die Phasen, die es gibt.** P14 bis P16 sind gebaut und
abgenommen; im Bauplan endete die Liste bei P13.

**Die erste Veröffentlichung wartet auf P13** (Entscheidung vom 31.07.2026):
der Launch führt die Skizzen als Kernargument. Die Veröffentlichungsreste aus
P8 (Zertifikat, Vertrieb, Website, Betatest) laufen parallel weiter.

### Nachtrag vom selben Tag: das Fundament, nachgesehen

Auf die Durchsicht folgte die Frage, ob das Grundlegende der Anwendung
tatsächlich in Ordnung ist. Es war es nicht, und die Funde hatten untereinander
eine Form: **Die Kette hängt am Namen, nicht am Inhalt.** Ein erzeugtes Merkmal
verlor seinen Namen an eine Operation, die ihr Feld leer ließ — lautlos, ohne
Befund. Eine gesenkte Bohrung verlor die **ganze** Bohrung, weil Kegelwand und
Bohrungswand ein Fleck waren. Ein eigener Baustein, dessen Maß der Nutzer
ändert, behält Name und Parameter, und der Hash sieht nichts. Dreimal derselbe
Bau, drei verschiedene Ecken.

Geändert haben sich daraufhin **§21.1** (der Kegel ist eine Merkmalsart; ein
Fleck endet an einer Kante; die Normalen entscheiden die Form, der Rückstand
die Güte), **§15.7** (der Weg, den eine Antwort nimmt — derselbe, den die
Rückfallstufen gehen), **§24.4** (für einen eigenen Baustein trägt die
Änderungsmeldung nicht), **§31** (elf Zeilen mit gemessenen Werten, zwei neue
Regeln über Zielwerte und Streuung, der Anwendungsstart in kalt und warm),
**§35** (keine Testart fragt, ob etwas angeschlossen ist), **§38** (der
Ergebnis-Cache in seinem eigenen, versionierten Ordner) und **§41** (Kugel und
Torus statt „Grundformen"). §18.5 hat die Auswahltiefe bekommen.

Der teuerste Einzelfund gehört nicht in eine dieser Zeilen: Der Plattencache
aus §38 war vollständig gebaut, vollständig geprüft und **in der Anwendung
nicht angeschlossen** — jedes Öffnen rechnete den ganzen Stapel neu, und kein
Test schlug an, weil jeder von ihnen sein Modul prüfte. Angeschlossen öffnet
dasselbe Projekt beim zweiten Mal in 209 statt 5063 Millisekunden. Was daraus
folgt, steht in §35 und ist unbequemer als die Zahl.

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

Die Anwendung ist vielseitig — genau deshalb muss die Oberfläche einfach
bleiben. Vielseitigkeit gehört in die Tiefe, nicht an die Oberfläche.

### 2.1 Das Versprechen

**Nichts ist endgültig.** Jede Handlung ist eine Op, jede Op ist rücknehmbar,
jeder Wert nachträglich änderbar. Das ist der eigentliche Gewinn des
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
Neues Projekt → beschreiben, was gebraucht wird → Agent legt Parameter an und
setzt Bausteine → Parameterleiste zeigt die Hauptmaße → an den Zahlen drehen,
Modell folgt sofort → exportieren.

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

**Nachgetragen am 18.08.2026.** Dieser Abschnitt führte drei Wege, während der
vierte längst gebaut war (P16): *Formen* und *Skelett* stehen in der oberen
Werkzeugleiste, das Beispielprojekt `weg4-figur-formen` liegt bei, und das
Handbuch hat sein Kapitel. Der Bauplan war die letzte Unterlage, die ihn nicht
kannte — gefunden bei der Durchsicht vom 17.08.

Diese vier Wege sind je ein Beispielprojekt (§37) und je eine
Abnahmeprüfung (§40).

### 2.3 Die ersten fünf Minuten

- **Kein leerer Startbildschirm.** Zuletzt geöffnete Projekte, die drei
  Beispielprojekte, ein großes Ablagefeld für Dateien.
- **Ziehen und Ablegen funktioniert überall** — auf das Fenster, auf den
  Viewport, auf den Objektbaum.
- **Die Erstinbetriebnahme fragt das Nötigste** (Sprache und Drucker) und
  übernimmt die im Slicer eingelegten Filamente samt Typ und Farbe. Das
  Material wird hier nicht ein zweites Mal gefragt. Alles andere bleibt auf
  Vorgaben stehen. Sie ist übersprings- und jederzeit nachholbar.
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

Sechs Bereiche wären zu viel für ein Fenster. Deshalb ein festes Schema mit
höchstens drei sichtbaren Zonen:

```
┌──────────────────────────────────────────────────────────┐
│ Werkzeugleiste                                           │
├──────────────┬───────────────────────────┬───────────────┤
│ Links        │                           │ Rechts        │
│ ┌──────────┐ │                           │ ┌───────────┐ │
│ │Objektbaum│ │        Viewport           │ │  Chat     │ │
│ ├──────────┤ │                           │ │    oder   │ │
│ │Parameter │ │                           │ │ Prüfbe-   │ │
│ ├──────────┤ │                           │ │ richt     │ │
│ │Verlauf   │ │                           │ └───────────┘ │
│ └──────────┘ │                           │               │
├──────────────┴───────────────────────────┴───────────────┤
│ Statusleiste: Maße · Auswahl · Fortschritt · Warnungen   │
└──────────────────────────────────────────────────────────┘
```

- **Links** drei einklappbare Abschnitte, nicht drei Fenster
- **Rechts** ein Bereich mit Umschaltung zwischen Chat und Prüfbericht — beide
  gleichzeitig braucht niemand, und die Umschaltung springt automatisch zum
  Bericht, wenn eine Warnung entsteht
- **Rechts ist ganz ausblendbar.** Ein Tastendruck, und der Viewport ist
  Vollbild.
- Keine Betriebsarten, keine Umschaltung zwischen „Bearbeiten" und
  „Konstruieren". Es gibt einen Zustand, und der ist die Szene.

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

Vorgabe folgt der Slicer-Gewohnheit: linke Taste wählt, rechte oder mittlere
Taste dreht, Umschalt plus Ziehen schiebt, Rad zoomt auf den Mauszeiger. Zwei
Alternativschemata (CAD-typisch, Blender-typisch) stehen in den Einstellungen
— das kostet fast nichts und erspart Umgewöhnung.

---

## 3. Ausführungsmodell

Der Plan wird von einem Programmier-Agenten umgesetzt. Zeitaufwand ist kein
Kriterium; Eindeutigkeit und maschinelle Abnahme sind es.

- **Abnahmekriterien statt Zeitschätzungen.** Jede Phase in §40 endet mit
  Bedingungen, die grün sein müssen.
- **Tests sind die Definition von fertig.** Für jede Geometrieoperation
  existiert ein Test mit festem Eingangs-Mesh (§34) und erwarteten Kennzahlen.
- **Kleine Schritte.** Nach jedem Schritt läuft die vollständige Suite.
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
| Doku für Nutzer, dieser Bauplan | Deutsch |
| Commit-Nachrichten | **Deutsch** |

Ohne diese Festlegung entsteht ein Gemisch wie `bausteinRegistry` oder
`wall_staerke`. Der Konsistenztest prüft Bezeichner stichprobenartig gegen
eine Liste deutscher Stämme.

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
| Tauschbörse | `shared` | öffentlich geteilte Rezepte auf der Website (`shared_parts`, `SharedPart`) |
| Melden | `flag` | Beschwerde über einen fremden Beitrag der Tauschbörse |
| Lizenz | `licence` | Nutzungsrechte an einem öffentlich geteilten Rezept — **aber das Dataclass-Feld heißt `license`**: `shared-rules.json` leitet ihre Erlaubnisliste aus `dataclasses.fields(Recipe)` ab, der Feldname ist also zugleich Schlüssel in Regel- und Rezeptdatei, und `serialise.py` schreibt das Format schon so. Zwei Schreibungen wären dort eine Übersetzungsstelle zwischen Python und PHP. Technischer Schlüssel amerikanisch wie das Format, Oberflächentext britisch wie der Katalog (36 Substantive mit `licence` gegen 6 mit `license`, und die sechs sind Partizipien und ein Eigenname). Als Parametername bleibt `licence`, weil `license` ein Python-Builtin ist (ruff A002) |

Diese Zuordnung ist verbindlich. Ein neuer Begriff kommt zuerst in diese
Tabelle, dann in den Code.

---

## 5. Verteilungsmodell

| | |
|---|---|
| **Produkt** | Desktop-Anwendung, als Download veröffentlicht |
| **Online** | Website mit Doku und Downloads |
| **Online, optional** | gehosteter Generierungs-Backend für Nutzer ohne GPU |
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
| Ergebnis | parametrisch, maßhaltig | organisch, texturiert | modifiziertes Mesh |
| Ausführungsort | immer lokal | lokal oder Backend | immer lokal |

Säule A hat genau **eine** Ausgabeform: die Op-Liste aus Bausteinen und
Primitiven. Sie bleibt im Kern, ist schemageprüft, im Stack sichtbar,
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
║             Chat / Prüfbericht │ Statusleiste              ║
╚══════════════════════┬═════════════════════════════════════╝
                       │  einzige erlaubte Richtung ↓
╔══ core ═══════════════════════════════════════════════════════╗
║  Operationsregister (§10) — Quelle für alle Oberflächen       ║
║  Szenenmodell — Objekte, Parameter, Passungen, Op-DAG,        ║
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
    scene/         Szene, Parameter, Passungen, Op-DAG, Auswertung,
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

Die Signaturen, an denen sich alle Module ausrichten. Sie stehen in
`core/types.py` und werden vor der ersten Umsetzung festgelegt.

```python
# ---- Geometrie und Objekte -------------------------------------------
@dataclass(frozen=True)
class Feature:
    id: str  # "hole_3" — ein Präfix je Operation wird nicht vergeben, s. §21.2
    kind: Literal["hole", "face", "edge_loop", "pin", "cone", "sphere", "torus", "thread"]
    provenance: Literal["detected", "generated"]
    params: dict  # Durchmesser, Achse, Tiefe, Fläche …
    face_indices: tuple[int, ...]
    created_by: OpId | None  # welcher Schritt es erzeugte, None bei erkannten


@dataclass
class SceneObject:
    id: str
    name: str
    mesh: Mesh  # Hülle um manifold3d/trimesh
    kind: Literal["mesh", "brep"]
    features: dict[str, Feature]
    material_slots: list[MaterialSlot]
    created_by: int  # Op-Nummer
    visible: bool = True


@dataclass
class Scene:
    objects: dict[str, SceneObject]
    parameters: dict[str, Parameter]
    fits: list[Fit]
    profile: Profile
    report: Report


# ---- Operationen -----------------------------------------------------
@dataclass
class OpContext:
    scene: Scene  # nur lesend
    inputs: list[SceneObject]
    params: BaseParams  # validiertes Schema
    profile: Profile
    quality: Literal["draft", "fine"]
    seed: int | None
    progress: ProgressFn  # (fraction: float, text: str) -> None
    ask: AskFn  # (question: str, choices: list[str]) -> str
    cancelled: CancelToken


@dataclass
class OpResult:
    outputs: list[SceneObject]
    solver: SolverInfo | None  # verwendete Rückfallstufe
    findings: list[Finding]  # Warnungen und Hinweise für den Bericht


OpFn = Callable[[OpContext], OpResult]


# ---- Schichtanalyse (§22) --------------------------------------------
@dataclass(frozen=True)
class LayerInfo:
    z: float
    contours: tuple[Polygon, ...]
    area: float
    overhang_area: float
    islands: tuple[Polygon, ...]
    min_width: float


@dataclass(frozen=True)
class SliceResult:
    layers: tuple[LayerInfo, ...]
    support_volume: float
    first_layer_area: float
    source: Literal["internal", "gcode"]  # nie vermischen (§22.5)


# ---- Skizzen (§30.1) -------------------------------------------------
@dataclass(frozen=True)
class SketchElement:
    kind: Literal["line", "arc", "circle", "point"]
    points: tuple[tuple[float, float], ...]  # Bedeutung je kind


@dataclass(frozen=True)
class SketchConstraint:
    kind: Literal[
        "distance",
        "coincident",
        "horizontal",
        "vertical",
        "parallel",
        "perpendicular",
        "tangent",
        "symmetric",
        "fixed",
    ]
    targets: tuple[int, ...]  # Punktindizes über die flache Punktliste der Skizze
    value: str = ""  # Maß als Ausdruck der Grammatik (§13), kein eval


@dataclass(frozen=True)
class Sketch:
    plane: str  # "plane:xy" | "plane:xz" | "plane:yz" | "feature:<id>"
    elements: tuple[SketchElement, ...]
    constraints: tuple[SketchConstraint, ...]


def solve_sketch(sketch: Sketch, params: "ParameterValues") -> "SolvedSketch":
    """Deterministisch, ohne Zufall. Unterbestimmt meldet die Freiheitsgrade
    als Befund; überbestimmt oder widersprüchlich hält an und nennt das
    kollidierende Bedingungspaar (Regel 17)."""
```

**Vier Regeln, die aus diesen Verträgen folgen:**

1. **`OpContext.scene` ist nur lesend.** Eine Op erzeugt neue Objekte, sie
   ändert keine bestehenden. Damit ist Leitprinzip 2 in der Typebene verankert.
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
    deterministic=True,
    shortcut="Ctrl+Shift+B",
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

**Konsistenztest**: Jede Op erscheint in allen Ausgaben, besitzt Schema,
Geometrietest und übersetzte Texte; kein Kürzel doppelt; nicht-deterministische
Ops führen einen Startwert; `applies_to` nennt nur bekannte Feature-Arten.

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
| `EPS_MATCH` | relativ, ~0,5 % der Modelldiagonale | Feature-Vergleich |

Merkregel: **absolut für Fertigung, relativ für Vergleiche.** Gerundet wird nur
in der Anzeige. Fließkommazahlen werden nie mit `==` verglichen.

### 11.3 Determinismus
**Drei Stellen sind randomisiert**: Jitter-Rückfallstufe (§17.2),
Farbquantisierung (§20) und die konvexe Zerlegung beim Auto Split. Jede bekommt
einen **Startwert, der in der Op gespeichert wird**, ist im Register als
`deterministic=False` gekennzeichnet und liefert bei gleichem Startwert
dasselbe Ergebnis. Ohne diese Regel ist Leitprinzip 4 nicht haltbar und ein
Fehlerbericht reproduziert nichts.

Es waren vier. Die **Abtastung der Orientierungssuche** ist mit §28.2
herausgefallen: Wer seine Kandidaten aus den Flächen der konvexen Hülle nimmt,
würfelt nicht mehr. Eine gewürfelte Stelle, die eine bessere Kandidatenwahl
erledigt, ist der angenehmste Weg, eine loszuwerden — sie verschwindet, statt
abgesichert zu werden.

**Nebenläufigkeit ist keine vierte Stelle, aber sie kann eine werden.** Die
Schichtanalyse misst auf so vielen Threads, wie die Maschine hat (§31). Das
bleibt reproduzierbar, solange jeder Thread eine Schicht für sich rechnet und
die Summen in feststehender Reihenfolge gebildet werden. Eine Reduktion, die in
der Reihenfolge der Fertigstellung addiert, ist es nicht — Fließkommaaddition
ist nicht assoziativ, und der Unterschied steht dann in der letzten Stelle
eines Volumens, das ein Bericht ausweist. Wer eine Rechnung parallelisiert,
prüft sie mit demselben Test, der zweimalige Auswertung vergleicht (§15.1).

---

## 12. Szenenmodell

```json
{
  "format_version": 14,
  "app_version": "0.2.2",
  "libs": {"manifold3d": "3.5.2", "trimesh": "5.0.0"},
  "parts_version": "12",
  "scene": {"printer": "centauri-carbon-2", "material": "petg"},
  "parameters": {
    "breite": {"value": 84.0, "unit": "mm", "min": 40, "max": 200,
               "title": "Breite", "title_translatable": true},
    "hoehe": {"value": 22.0, "unit": "mm", "min": 10,
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
    {"name": "stift_1", "a": "obj_2:op5.pin_1", "b": "obj_3:op5.hole_1",
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
     "params": {"axis": "z", "position": "=@hoehe/2", "pins": 3,
                "diameter": 4.0, "play": "auto:petg"},
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

Der DAG über `in`/`out` bildet hier das Teilen (1 → 2) ab und kann ebenso ein
Vereinigen (2 → 1) tragen; der Stack bleibt linear darstellbar. Drei
Indirektionen tragen das Modell:
`"auto:petg"` für Toleranzen, `"=@hoehe/2"` für Parameter (§13), `solver` und
`seed` für Reproduzierbarkeit (§11.3, §17.2).

---

## 13. Projektparameter

Benannte Größen auf Szenenebene, auf die Ops verweisen. Damit wird aus jedem
Projekt eine Vorlage: „dieselbe Halterung, andere Maße" ist ein Zahlendialog
statt einer neuen Sitzung.

- **Verweis** `"@breite"` oder Ausdruck `"=@breite/2 - @wandstaerke"`
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
{"name": "stift_1", "a": "obj_2:op5.pin_1", "b": "obj_3:op5.hole_1",
 "type": "clearance", "tolerance": "auto:petg"}
```

- **Arten**: `clearance` (Spiel), `press` (Presspassung), `thread` (Gewinde),
  `flush` (bündig, für Flächen)
- **Prüfung bei jeder Auswertung**: Entspricht die Differenz der
  Profiltoleranz im Rahmen von `EPS_GEOM`? Verletzungen erscheinen im
  Prüfbericht, im Steckbrief und als Analysekarte (§18.4), nie stillschweigend.
- **Auto Split legt die Paare automatisch an** — dort entstehen sie ohnehin.
- **Der Agent kann Paare anlegen**; die Suite prüft, ob er es tut.

---

## 15. Auswertung und Neuberechnung

### 15.1 Auswertung als reine Funktion
`Stack + Quellen + Parameter + Profile + Startwerte → Szene`. Kein versteckter
Zustand, keine Seiteneffekte. Zweimal ausgewertet ergibt zweimal dasselbe.

### 15.2 Geänderte Objektzahl
Liefert eine Op nach einer Änderung mehr oder weniger Objekte als zuvor:
gleiche Anzahl → Bindung über die Position in `out`; abweichende Anzahl →
nachfolgende Ops, die auf entfallene Objekte zeigen, gelten als
**unerfüllbar**, die Kette hält an, der Nutzer wählt zwischen neu zuordnen und
verwerfen. Kein automatisches Nachrücken.

### 15.3 Angehaltene Kette
Der Viewport zeigt **den letzten vollständig gerechneten Zustand**, nie ein
leeres Fenster, dazu einen Hinweis in der Statusleiste und die betroffenen Ops
im Verlauf markiert. Alles davor bleibt bedienbar.

### 15.4 Keine Verzweigungen
Eine Änderung nach einem Undo verwirft die abgeschnittenen Ops — mit
Rückfrage, sobald es mehr als eine ist. Verzweigungen stehen in §41.

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
Manuelle Operationen sind Einzeltransaktionen. Die Transaktion trägt Titel und
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

### 15.7 Antworten auf Rückfragen sind Parameterwerte
Regel 21 verlangt anzuhalten und zu fragen, statt zu raten — über `ctx.ask`
(§9). Damit steht die Frage, wohin die **Antwort** gehört, und §15.1 lässt nur
eine Möglichkeit offen: Die Auswertung ist eine reine Funktion aus Stack,
Quellen, Parametern, Profilen und Startwerten. Eine Antwort, die nur in der
Sitzung lebt, wäre ein sechster Eingang, den niemand aufgeschrieben hat —
zweimal ausgewertet käme zweimal etwas anderes heraus, und genau dieser
Vergleich ist ein Abnahmekriterium von P0.

**Also wird die Antwort in die Parameter der fragenden Operation geschrieben,
und die Operation gilt damit als geändert.** Zwei Stellen sagen das bereits für
ihren Einzelfall: Die Einheitenrückfrage ist ein Parameter der Op `load`
(§17.1), und bei mehrdeutiger Feature-Zuordnung „wird die Op umgeschrieben"
(§21.3). §15.7 ist dieselbe Regel ohne Einzelfall — und sie hat zwei Folgen,
die man wollen muss: Die Antwort reist mit der Projektdatei, und die Operation
gilt danach als geändert, gehört also gespeichert.

**Eine dritte stand hier und war falsch:** dass ein Undo die Antwort mitnimmt.
Sie bekommt **keine eigene Transaktion**, denn sie ist keine neue Handlung,
sondern der Abschluss der einen, die gefragt hat. Als Transaktion nähme ein Undo
sie zurück, die Frage käme wieder, und der Verlauf füllte sich mit Einträgen,
die keine Handlung beschreiben. Das ist derselbe Weg, den `change_params` seit
je nimmt: Eine Bohrung zwei Millimeter weiter links ist dieselbe Operation mit
einer anderen Zahl und kein Schritt zum Zurücknehmen.

Der Preis dafür, dass es nicht dastand, ist gemessen: Eine Bauplatte mit 52
Teilen stellte über die ganze Kette **99 modale Fenster für 7 Entscheidungen**
— sechzehnmal dieselbe Frage nach `pin_1`, weil die Antwort nirgends blieb.
Anhalten und fragen ist richtig; dieselbe Frage bei jeder Auswertung erneut zu
stellen, ist keine Vorsicht, sondern ein fehlender Speicherort.

**Der Weg dorthin war schon gebaut, für etwas anderes.** Die Auswertung ist eine
reine Funktion und darf das Dokument nicht ändern — sie kann die Antwort also
nicht selbst hineinschreiben. Genau dieselbe Lage haben die Rückfallstufen
(§17.2), und sie ist gelöst: Das Ergebnis der Auswertung führt sie mit, und der
Aufrufer schreibt sie in den Stapel zurück. Antworten gehen denselben Weg — ein
Feld daneben, ein Rückschreiben daneben —, **mit einem Unterschied, der die
Sache ausmacht: Eine Rückfallstufe ist ein Vermerk, den die Auswertung nie
zurückliest. Eine Antwort ist eine Anweisung.** Wird sie nicht geschrieben,
stellt der nächste Lauf dieselbe Frage.

**Zwei Sorten sind zu tragen, und nur die erste ist gebaut.**

*Was eine Operation selbst erfragt hat* — die Einheit in `load` (§17.1) — steht
seit dem 22.08.2026 im Stapel. Die fragende Operation gibt sie zurück, denn nur
sie weiß, welchen ihrer Parameter die Antwort betrifft; die Auswertung sieht
allein, **dass** gefragt wurde. Das kostet einmal je Frage eine Neuberechnung
des Zweiges darunter, weil sich der Operations-Hash ändert — und danach nie
wieder.

*Was die Zuordnung entschieden hat* (§21.3) ist offen, und es geht nicht
denselben Weg: Welches neu erkannte Merkmal einen alten Namen erbt, ist **keine
Eingabe der Operation**, also gibt es dafür keinen Parameter, und die
Schemaprüfung würde einen erfundenen Schlüssel abweisen. Es braucht ein eigenes
Feld an der Operation, neben `solver` und `seed` — und `seed` ist dabei der
Präzedenzfall mit dem besseren Argument: **ein Wert auf Operationsebene, der
eine nicht selbst reproduzierbare Prozedur reproduzierbar macht.** Genau das tut
eine festgehaltene Antwort. Damit ist es eine Formatänderung (§16.2), und die
Fünf-Schritte-Checkliste gilt.

Dabei gibt es zwei Fallen, die schon gefunden sind. **Ein Bezeichner ist kein
brauchbarer Speicherwert**: Nummeriert die Erkennung im nächsten Lauf anders,
zeigt die gespeicherte Antwort auf ein anderes Merkmal — aus „fragt zu oft"
würde „nimmt stillschweigend das falsche", und das ist die schlechtere Hälfte
des Tauschs. Festgehalten wird deshalb, **welches** Merkmal gewählt wurde, an
seiner Lage, seiner Achse und seinem Maß. **Und das braucht ein Netz:** Trifft
der festgehaltene Abdruck keinen Kandidaten mit Abstand vor dem zweiten, wird
wieder gefragt. Ohne diesen Abstand hat man dieselbe Mehrdeutigkeit ein zweites
Mal, nur ohne sie zu bemerken — sie war ja gerade deshalb mehrdeutig, weil zwei
Kandidaten sich fast gleichen.

**Und es ist keine Bequemlichkeit mehr, seit es einen Plattencache gibt** (§38).
Solange die Antwort nur in der Sitzung lebte, war sie beim nächsten Start eben
wieder fällig — ärgerlich, aber ehrlich. Kommt das Ergebnis von der Platte, wird
die Frage **nicht mehr gestellt**: Der Nutzer bekommt stillschweigend eine
Annahme statt einer Rückfrage, und Regel 21 ist verletzt, ohne dass irgendwo ein
Befund entsteht. Schlimmer noch, es wäre **nicht einmal verlässlich falsch** —
ob gefragt wird, hinge daran, ob eine Cache-Datei überlebt hat, und die darf
jederzeit gelöscht werden.

Deshalb gilt bis zur Umsetzung, und danach als Wächter weiter: **Ein Ergebnis,
dessen Auswertung `ctx.ask` gerufen hat, geht nicht über die Sitzung hinaus.**
Im Speicher bleibt es — dort wird innerhalb einer Sitzung nicht zweimal gefragt
—, auf die Platte nicht. Das gilt für beide Fragesteller: die Operation selbst
(die Einheit in `load`) und die Zuordnung bei einem mehrdeutigen Merkmal
(§21.3), und für den zweiten greift er heute noch.

**Dass er nicht mehr greift, ist die Prüfung für den Rest von §15.7** — und sie
ist besser als eine, die in die Innereien sieht: Nicht „die Antwort steht im
Stapel", sondern „keine Operation gibt mehr zurück, dass ihr Ergebnis in der
Sitzung bleiben muss". Wird das nie mehr wahr, ist keine Antwort mehr
unaufgeschrieben. Danach bleibt der Wächter stehen, für die nächste Operation,
die zu fragen anfängt, ohne es aufzuschreiben.

---

## 16. Projektdatei

### 16.1 Container
```
projekt.p3d           (ZIP)
  project.json        # Stack, Parameter, Passungen, Transaktionen
  sources/            # eingebettete Quell-Meshes
  report.json         # letzter Prüfbericht
  thumb.png           # Vorschaubild für Dateidialoge
```
Quellen wahlweise eingebettet oder verlinkt; **für die Weitergabe ist
Einbetten die Vorgabe**. Prüfsummen in beiden Fällen, beim Laden verifiziert.

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
- **Ein Fehlerbericht ist der Container** — er reproduziert den Fehler exakt,
  einschließlich Startwerten und Rückfallstufen

### 16.3 Herkunft importierter Modelle
Heruntergeladene Modelle tragen Lizenzen, oft mit Einschränkung für
kommerzielle Nutzung. Jede Quelle kann `origin` führen: URL, Titel, Urheber,
Lizenz, Abrufdatum. Beim Import anbieten, nicht erzwingen. **Beim Export ein
Hinweis**, wenn eine beteiligte Quelle eine Einschränkung trägt — einmal,
sachlich, ohne Belehrung.

---

## 17. Eingangsstufe und Rückfallketten

### 17.1 Eingangsstufe
Jede geladene Datei durchläuft dieselbe Kette; das Ergebnis steht in `sources`:

1. **Einheit bestimmen.** STL kennt keine Einheiten. Heuristik über die
   Bounding Box; bei Verdacht **nachfragen** statt annehmen.
2. **Vertices verschweißen** mit `EPS_GEOM`, skaliert an der Modellgröße.
3. **Entartete Dreiecke entfernen** (Nullfläche, Nadeln, Dubletten).
4. **Normalen vereinheitlichen**, Orientierung prüfen.
5. **Komponenten zählen**, Kleinstteile melden statt still zu löschen.
6. **Lage**: Schwerpunkt ermitteln, Aufsetzen auf das Bett anbieten — nicht
   erzwingen.

Die Eingangsstufe ist die Op `load`, damit ihre Parameter im Stack sichtbar und
änderbar bleiben.

### 17.2 Rückfallkette für Boolesche Operationen

| Stufe | Verfahren | Vermerk |
|---|---|---|
| 1 | direkt | `direct` |
| 2 | verschweißen, Toleranz erhöhen, erneut | `welded` |
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

Kein Anzeigefenster, sondern das Prüfwerkzeug.

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
| Krümmung | Kanten und Verrundungen | Feature-Erkennung prüfen |
| Feature-Zuordnung | jedes Feature eigen eingefärbt | verstehen, was die KI sieht |
| Passungen | verbundene Paare, Verletzungen markiert | Mehrteiliges prüfen (§14) |
| Stützbedarf | aus der Schichtanalyse (§22), fein aus dem G-Code (§28) | Orientierung beurteilen |

Immer mit Legende und Zahlenbereich, Paletten nach §19.1. Jede Karte ist auch
über den Prüfbericht erreichbar: Klick auf eine Warnung schaltet die passende
Karte ein und fährt die Kamera auf die Stelle — der kürzeste Weg von „es gibt
ein Problem" zu „hier ist es".

### 18.5 Feature-Overlay
Erkannte Bohrungen und Flächen farbig, mit Beschriftung (`hole_3 · Ø4.2`), beim
Überfahren hervorgehoben, beim Anklicken ausgewählt, als Referenz im Chat und
als Kontextmenü mit den passenden Ops (§10, `applies_to`).

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
Zusammenhangskomponenten.

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

**Ein Zylinder**ausschnitt** ist keine Bohrung und kein Zapfen, sondern eine
Verrundung.** Getrennt wird an der Überdeckung um die Achse: Bohrungen und
Zapfen überdecken 345 bis 356 Grad, eine verrundete Quaderkante 90 — dazwischen
liegt über den ganzen Korpus nichts. Ohne diese Trennung las der Kunde „Zapfen
Ø 6" an dem, was er als „Verrundung R 3" kennt, und `applies_to` bot ihm
Passungs-Operationen an; §14 nennt einen Zapfen aber das, womit man eine
Bohrung paart, und mit einer Kantenverrundung paart niemand etwas.

**Nur die gerade Kante.** An einer runden ist die Verrundung ein Torusstück,
und ihr Radius steht dort bereits als Röhrenradius — aber ein Kehlstück ist von
einem vollen Ring über die Überdeckung nicht zu trennen, und eine Schwelle, die
sich nicht messen lässt, gehört nicht gebaut. Der Fall bleibt offen und ist als
solcher benannt.

**Die Reihenfolge der Prüfungen ist Teil der Aussage.** Kugel und Torus kamen
am 22.08.2026 dazu, und sie werden erst gefragt, wenn Zylinder und Kegel
abgelehnt haben — nicht daneben. Der Fall, der das erzwingt: Eine 90°-Senkung
passt auf eine **Kugel** mit einem Rückstand von 0,054 und damit unter der
Schwelle, die für Zylinder und Kegel gilt; eine echte Kalotte liefert 0,0003.
Deshalb steht dort eine eigene, strengere Schwelle (`ROUND_TOLERANCE`, 0,02),
und deshalb kommt die Frage zuletzt. Ein `hole_1`, das plötzlich `sphere_1`
hieße, wäre für jede Bohrungs-Operation unsichtbar.

**Ein Torusstück misst die Einpassung seit dem 22.08.2026**, und zwar bis
herunter zu etwa einem Achtelring: Achse aus den Normalen, Achsenpunkt aus
einem zweiten linearen System, beide Radien aus dem **Meridiankreis** — der
Meridianschnitt eines Torus ist ein Kreis, und eine Kreiseinpassung braucht
keinen ganzen Kreis. Darunter meldet es der Rückstand, und die Form wird
abgelehnt statt geraten.

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

**Importierte Features — Zuordnung.** Nach jeder Op läuft die Erkennung neu.
Alt und neu werden über einen Merkmalsvektor (Typ, Durchmesser,
Achsenrichtung, Position im Objektsystem, Nachbarschaft) optimal zugeordnet —
ungarische Methode über die Kostenmatrix, Schwelle `EPS_MATCH`.

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
Ebene-Mesh-Schnitt je Höhe über eine sortierte Kantenliste, die Schnittsegmente
zu geschlossenen Polygonen verkettet. Für Flächen- und Offsetrechnungen
Clipper2 (Boost-Lizenz, unkritisch). Kein Fremdprozess, keine Installation,
Ergebnis in Millisekunden statt Sekunden.

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

- **Orientierungssuche**: statt drei bis fünf vorgefilterte Kandidaten extern
  zu slicen, lassen sich **hunderte Rotationen** durchrechnen und nach echtem
  Stützvolumen sortieren.
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
| Geschwindigkeit | Millisekunden | Sekunden |
| Ergebnis | Kennzahlen, Konturen | G-Code |
| Voraussetzung | keine | Installation |
| Verbindlich für | Iteration und Optimierung | die Druckdatei |

Die Kennzahlen beider Wege werden **nie vermischt**. Der Prüfbericht weist
aus, woher ein Wert stammt — ein geschätztes Stützvolumen aus der
Schichtanalyse ist etwas anderes als ein gemessenes aus dem G-Code.

---

## 23. Steckbrief für den Agenten

```
Szene: 2 Objekte, Drucker centauri-carbon-2, Material PETG (kalibriert)
Parameter: breite=84.0 mm, hoehe=22.0 mm, wandstaerke=2.4 mm
Auswahl: obj_2 · hole_3
obj_2  "halterung_oben"  84 × 40 × 11 mm, 14.1 cm³, wasserdicht, auf Bett
  face_1  planar 84×40, Normale -Z   (Aufstandsfläche)
  hole_3  Ø 5.2 mm, Achse +Z, Durchgang, auf face_1
  op3.heatset_1  Baustein heatset_m4, auf face_1
  op5.pin_1      Ø 4.0 mm, Achse +Z, Zapfen   → Passung stift_1
  hinweis Op 5 über Rückfallstufe "voxel" gelöst — Maße gerundet
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
    title=_("Heat-Set-Einpressbuchse M4"),
    params=HeatsetParams,
    features=["bore", "chamfer"],
    preview="heatset_m4.png",  # für den Katalog (§2.6)
    doc=_("Bohrung für eine Einpressbuchse M4 mit Einführfase."),
)
def heatset_m4(params: HeatsetParams) -> PartResult: ...
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

Jeder Baustein wird über seinen Parameterbereich durchgerechnet: wasserdicht,
Mindestwandstärke, keine Selbstdurchdringung an den Grenzen, Features korrekt
benannt. Ein Baustein ohne diesen Test gilt als nicht vorhanden.

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
  **Für einen eigenen Baustein (§24.5) trägt dieser Weg nicht**, und das ist
  eine offene Stelle und keine Ausnahme: Die Prüfung liest die gepflegten
  Änderungsverläufe, und wer an seinem eigenen Baustein ein Maß ändert und
  speichert, pflegt keinen. Was sie stattdessen lesen müsste, ist der Zustand
  der Dateien selbst — Name, Änderungszeit, Größe unter
  `<Nutzerdaten>/parts/`. Genau diese Auskunft braucht auch der Plattencache
  (§38), um für einen geänderten eigenen Baustein nicht das alte Ergebnis
  zurückzugeben; sie wird also ohnehin gebildet
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
  nutzbar.** Die optionale öffentliche Community-Tauschstelle auf der Website
  ist eine kostenlose Ablage für sichere Rezepte und **kein Marktplatz**. Ihr
  Startumfang ist: Rezepte suchen, ansehen, hochladen und herunterladen. Es
  gibt dort keine Konten, Profile, Zahlungen, Provisionen oder
  Direktnachrichten; Likes und Kommentare gehören nicht zum Startumfang
- Öffentlich getauschte Rezepte führen **keine eingebetteten Modelldaten oder
  sonstigen Mesh-Payloads** mit. Lokal dürfen solche Daten in Projektdateien
  weiterhin mitreisen. Für jeden öffentlichen Beitrag bleiben ausgewiesene
  Herkunft und Lizenz, die serverseitige Erlaubnisprüfung sowie ein Melde- und
  Entfernungsweg verpflichtend
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
Primitive einfügen; **Baustein an ein erkanntes Feature setzen** (§24)

**Skizze** (§30.1, B-Rep) — Grundform anlegen (Rechteck, Langloch, Kreisbild,
Vieleck), Skizze extrudieren, rotieren, als Tasche schneiden, entlang Pfad
führen

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

Einschränkung, solange nur der Mesh-Kern läuft: **Verrundungen und Fasen auf
beliebigen Mesh-Kanten bleiben hart.** Mit dem B-Rep-Kern (§30) fällt sie.

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
und zwar lautlos: Es kommt keine Fehlermeldung, es kommt eine Rechnung. Die
Werkzeugschemata allein sind über hundert Kilobyte.

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
**Jeder Chatbeitrag verweist auf die Transaktion, die er erzeugt hat.** Wird
sie zurückgenommen, gilt der Beitrag als **verworfen** und geht beim nächsten
Kontextaufbau höchstens als „wurde verworfen" mit; Redo stellt ihn wieder her.
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
die Menüs — über JSON-RPC nach dem Model-Context-Protocol. Die Werkzeuge kommen
aus derselben Liste wie die des Chats; es gibt keine zweite und keinen zweiten
Weg ins Dokument.

Fünf Auflagen, jede mit Test:

1. **Standardmäßig aus**, Schalter in den Einstellungen.
2. **Nur `127.0.0.1`** — geprüft an der Bindung *und* an jeder Anfrage.
3. **Kein ausführbarer Quelltext, kein Dateipfad**, abgewiesen vor der
   Rechnung. Der Pfad wird am Wert erkannt, nicht am Parameternamen.
4. **Jeder Aufruf eine Transaktion** mit Herkunftsvermerk (§26.4), rücknehmbar
   wie jede andere.
5. **Die Herkunft jeder Anfrage wird geprüft, nicht nur die Bindung.** Eine
   Bindung an `127.0.0.1` hält keinen Browser ab: Ein Skript auf einer fremden
   Seite lässt den Namen seiner eigenen Adresse auf `127.0.0.1` umschwenken und
   spricht danach aus dem Browser des Nutzers mit dem lokalen Server — von
   innen, mit dessen Rechten, und mit jedem Werkzeug, das die Liste hergibt.
   Das Protokoll verlangt deshalb, den `Origin`-Kopf gegen eine Liste zu prüfen
   und eine fremde Herkunft mit 403 abzuweisen; eine Anfrage **ohne** `Origin`
   kommt aus keinem Browser und geht durch. Auflage 2 allein war das nicht.

Auflage 5 stand bis zu dieser Fassung nicht hier, obwohl die Umsetzung sie seit
P15 erfüllt. Das ist die unangenehmere Richtung des Auseinanderlaufens: Ein
Bauplan, der lockerer ist als der Code, sieht nach nichts aus — bis jemand ihn
für die Wahrheit nimmt und die Prüfung als überflüssig entfernt.

---

## 27. Backends

**LLM** — Standard ist der eigene Schlüssel des Nutzers im
System-Schlüsselbund. Alternative: lokal über Ollama; zuverlässiges
Tool-Calling braucht ein ausreichend großes Modell, kleine scheitern
reproduzierbar. Empfehlungsliste in die Doku. Ohne Schlüssel sind
Agentenfunktionen ausgegraut, die Anwendung bleibt voll nutzbar.

**Mesh-Generierung** — lokal über ComfyUI oder gehostet gegen denselben Aufruf.
Die Schnittstelle kennt nur `text_to_mesh` und `image_to_mesh`: kein
Nutzercode, keine Dateipfade, kein Zustand.

**Der gehostete Dienst, falls er kommt**, bleibt klein: nimmt Text oder Bild,
gibt ein Mesh zurück, sonst nichts. Keine Projektablage, keine Historie.
Eingaben nach Auslieferung löschen, nicht für Training verwenden, und das auch
so hinschreiben. Abrechnung über Guthaben, Warteschlange mit Zeitlimit,
Serverstandort in der EU.

---

## 28. Rückkopplung aus Slicer und Drucker

Die Schichtanalyse (§22) sucht und bewertet, der externe Slicer liefert die
Wahrheit für die Druckdatei. Beide Wege bleiben getrennt ausgewiesen.

### 28.1 G-Code zurücklesen
Druckzeit, Materialverbrauch, **gemessenes Stützmaterialvolumen**, Schichtzahl,
Warnungen — als Gegenprobe zur internen Schätzung und als Grundlage der
Kostenschätzung.

### 28.2 Was das ändert
Die Suche selbst läuft intern über §22 — hunderte Kandidaten statt einer
Handvoll. Der externe Lauf dient nur noch der **Bestätigung der Siegerlösung**
und der Kostenschätzung. Das kehrt das Verhältnis um: früher war der Slicer der
Flaschenhals der Suche, jetzt ist er die Endabnahme.

**Woher die Kandidaten kommen, entscheidet mehr als ihre Zahl.** Hier stand
„hunderte Rotationen", und die Umsetzung füllte sie mit gleichmäßig über die
Kugel gestreuten Zufallsrichtungen auf. Das ist die teurere Hälfte einer
schlechteren Suche: Ein Körper liegt nur auf einer Fläche seiner **konvexen
Hülle** — jede andere Richtung beschreibt eine Lage, in der er umkippt, und
wird trotzdem durchgerechnet. Die Kandidaten sind deshalb die Flächennormalen
der konvexen Hülle, nach Fläche geordnet, dazu die sechs Achsrichtungen und die
Normalen der großen ebenen Flächen des Körpers selbst.

Das ist dreimal besser und einmal billiger: Es sind weniger Kandidaten, jeder
einzelne ist eine mögliche Lage, keine gute Lage fällt durch das Raster — und
es ist **deterministisch**, womit eine der gewürfelten Stellen aus §11.3
entfällt. Bei einem organisch gewachsenen Körper ist es der Unterschied
zwischen Suchen und Raten: Er hat keine große ebene Fläche, an der die alte
Liste ihn erkennen könnte; seine Hülle hat sie.

Weicht die Gegenprobe deutlich von der internen Schätzung ab, ist das ein
Befund im Prüfbericht — und ein Hinweis, dass die Schichtanalyse nachgebessert
werden muss.

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

**Plattenbelegung.** Die Anordnung legt die Körper in Zeilen, und das war eine
Entscheidung für Vorhersagbarkeit: Ein Packen, das jeder nachvollziehen kann,
schlägt ein kluges, das Teile aus Gründen verschiebt, die niemand sieht. Der
Preis ist gemessen — **52 Teile auf sieben Platten**, und das ist zu viel. Die
Entscheidung lautet deshalb: **Die Vorhersagbarkeit bleibt, die Zeilen gehen.**

Der Fehler steckt nicht in der Reihenfolge, sondern in der Struktur. Zeilenweise
zu packen heißt, hinter jedem flachen Teil einen Streifen zu verschenken, der
so tief ist wie das tiefste Teil derselben Zeile; eine andere Sortierung verschiebt
diesen Streifen nur — nach Tiefe sortiert wurde es nachweislich nicht besser.
Was ihn beseitigt, ist eine Regel ohne Zeilen: **jeder Körper an die hinterste,
dann linkeste freie Stelle, an die er passt.** Das ist in einem Satz erklärbar,
deterministisch und ohne Startwert — es bleibt damit alles, wofür die Zeilen da
waren.

Die Abnahme ist eine Messung und keine Meinung: **weniger Platten für dieselben
52 Teile.** Wird es nicht weniger, bleibt es beim Zeilenpacken — dieselbe Regel
wie bei einer Änderung an der Regelsammlung (§39). Was aus der Anordnung fällt,
weil zu wenige Platten da sind, bleibt ein Befund und wird nie stillschweigend
weggelassen.

**Formate**: STL binär, **3MF mit Objektnamen, Anordnung und Farbgruppen**,
OBJ, PLY, GLB zum Zeigen, STEP bei B-Rep-Objekten.

**Namensschema** bei mehreren Teilen, konfigurierbar, Vorgabe
`<projekt>_<objekt>_1von3.stl`. Objektnamen werden dateisystemtauglich
gemacht, ohne unkenntlich zu werden.

**Übergabe an den Slicer**: direkt per Kommandozeile aufrufen oder die
exportierte Datei öffnen. Ordner, Format und Übergabeart werden je Projekt
gemerkt.

**Exportprüfung vor dem Schreiben**, als Bericht, nicht als Blockade:
wasserdicht, innerhalb des Bauraums, keine verletzten Passungen, keine
Dünnstellen unter der Mindestwandstärke, Lizenzhinweis beteiligter Quellen
(§16.3). Wer trotzdem exportieren will, kann das — er weiß dann nur, was er tut.

---

## 30. Zweiter Konstruktionskern (B-Rep)

Späte, aber geplante Stufe (build123d oder CadQuery, OpenCascade darunter):
echte Kanten und damit **echte Fasen und Verrundungen**, **STEP-Import und
-Export**, Skizzen mit Zwangsbedingungen, präzise Booleans ohne
Vernetzungsartefakte.

Als zweiter Kern **neben** dem Mesh-Kern, nicht als Ersatz. Objekte tragen die
Kennzeichnung `kind` (§9). Der Übergang B-Rep → Mesh ist jederzeit möglich, der
Rückweg nicht — im Objektbaum sichtbar machen.

Für die Feature-Erkennung ein Sprung: Bei B-Rep-Objekten entfallen Clustern und
ID-Problem weitgehend, weil Flächen und Kanten benannte Entitäten sind.

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

  **Spline und Referenz kamen später dazu** und standen bis zum 21.08.2026
  nur in der Roadmap. Ein Spline trägt eine Kurve, die sich nicht aus Bögen
  bauen lässt; eine Referenzbedingung ist ein Maß, das anzeigt statt
  festzulegen — sie ändert die Freiheitsgrade nicht und kann deshalb nie in
  einen Konflikt geraten. Nachgetragen bei der Durchsicht der Skizzen, weil
  eine Liste, die zwei Einträge zurückhängt, beim nächsten Abgleich als
  Widerspruch gelesen wird.
- **Die Skizze lebt als Parameterwert der Operation, die sie verbraucht**
  (`sketch_extrude`, `sketch_pocket`, `sketch_revolve`, `sketch_sweep`).
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
- **Zwei Ausgabestufen.** Stufe eins: die Grundformen über Dialog, CLI und
  Agent — voll parametrisch, ohne Grafikeditor. Stufe zwei: der grafische
  Editor im Viewport (Ebene anklicken, zeichnen, Bedingungen über
  Werkzeugleiste und Kontextmenü), offscreen testbar. Stufe eins ist für
  sich vollständig und abnahmefähig.
- **Die Skizzen-Ops rechnen gegen den B-Rep-Kern.** Ohne installiertes
  `brep` sagen sie das in einem Satz; alles andere bleibt benutzbar
  (bestehendes Muster aus P12).

---

## 31. Leistungsbudget

Gemessen auf dem Referenzkorpus (§34), als Teil der Suite protokolliert.

| Vorgang | Zielwert | gemessen |
|---|---|---|
| Viewport-Navigation | flüssig bei 1 Mio. Dreiecken | **im Tor nicht messbar** — braucht Bilder auf echter GL |
| Anzeigeaufbau, 1 Mio. → 200 000 Dreiecke | unter 4 s | 2,51 s — im Ziel |
| Anzeige-Dezimierung greift ab | 500 000 Dreiecken | Schwelle, keine Zeit |
| Boolesche Op, 200 000 Dreiecke | unter 2 s | 1,14 s — im Ziel |
| Feature-Erkennung, 200 000 Dreiecke | unter 1 s | 0,80 s — im Ziel |
| Analysekarte Wandstärke | unter 3 s, im Hintergrund | 1,43–1,48 s — im Ziel |
| Projekt öffnen aus Plattencache | unter 1 s | 0,56–0,67 s beim zweiten Öffnen, 4,87 s beim ersten |
| Parameteränderung → sichtbares Ergebnis | unter 2 s, nur betroffene Zweige | 8 ms — im Ziel, und die Zusage hält |
| Schichtanalyse, 200 000 Dreiecke, 0,2 mm | unter 300 ms | 288–299 ms auf exakt 200 000, Median 292 ms — im Ziel; 331–355 ms auf 327 680 |
| Skizzen-Solver, 200 Bedingungen | unter 100 ms | 48–50 ms — im Ziel |
| Orientierungssuche, 200 Kandidaten | unter 20 s, abbrechbar | 17,9 s — im Ziel, zweimal aber über 20 s |
| Anwendungsstart bis bedienbar, **kalt** | unter 3 s | 12,9 s vor dem verzögerten Geometrieimport — neue Kaltmessung steht aus |
| Anwendungsstart bis bedienbar, **warm** | unter 3 s | 1,48 s — im Ziel |

Die dritte Spalte führt die Bestwerte aus `tests/.performance.json`, überwiegend
vom 22.08.2026, auf Roberts Maschine und unter dem Schloss gemessen; der
Anwendungsstart wurde am 29.08.2026 nachgemessen (die Datei selbst reist nicht
mit — sie steht in `.gitignore`, also ist diese Spalte der einzige
nachprüfbare Ort). Sie steht hier, weil eine Tabelle aus reinen Zielwerten nach
zwei Jahren nicht mehr verrät, ob sie Absichten oder Zustände beschreibt. Was
sie zeigt, ist beides: **Alle Rechenzeilen halten**, eine kalte Messung steht
nach dem Umbau aus, und eine Ansichtszeile ist im Tor grundsätzlich nicht
messbar.

Drei Zeilen haben sich dabei geändert, und zwei davon nicht durch schnelleren
Code. *Anwendungsstart* ist zweigeteilt (siehe unten), *Projekt öffnen* hat
überhaupt erst einen Weg bekommen — der Plattencache war gebaut und nicht
angeschlossen (§38); gemessen ist die Zeile jetzt **durch die Anwendung**, also
zweimal `Session()`, importieren, speichern, öffnen, und nicht über einen
handgesetzten Cache-Eintrag. In den 560 ms steckt das Lesen eines
65-MB-Containers mit; die Auswertung selbst ist der kleinere Teil.
*Anzeigeaufbau* ist neu: Die Zeile darüber ist eine
Bildrate und im Tor nicht messbar, aber die eine teure Rechnung zwischen
„Körper geladen" und „navigierbar" ist es sehr wohl, und sie ist der Grund,
warum eine Million Dreiecke überhaupt flüssig gehen — gezeichnet werden 200 000.

**Das echte Fenster hat am 29.08.2026 den vermeintlichen Ansichtsengpass
widerlegt.** `dose-mit-deckel.p3d` brauchte vor der Korrektur 21,55 s bis zum
vollständigen Bild; davon entfielen nur 0,19 s auf den Viewport. 17,09 s lagen
in der Übertragung der Filamentflächen nach Booleschen Operationen: Eine
einzige große Fläche weitete die exakte Kandidatensuche auf 32,36 Millionen
Dreieckspaare. Nach Größenbändern sind es 224 432 Paare, dieselben Slotwerte
und 3,06 s bis zum vollständigen Bild. Die Kernauswertung allein fiel von
14,11 auf 1,53 s.

**Die drei knappen Rechenziele wurden am selben Tag nicht nur neu
beschriftet.** Der native Schichtkern verkettet jetzt nicht bloß fertige
Segmente, sondern schneidet die Dreiecke selbst: Der NumPy-Zwischenweg kostete
203 ms und mehrere große Felder, der übersetzte Weg 27–31 ms. Auf dem
327-680-Dreieck-Korpus fiel die ganze Analyse von 1,05 s ohne Kern zunächst auf
443–462 und jetzt auf 331–355 ms. Ein auf exakt 200 000 Dreiecke vereinfachter,
weiterhin geschlossener Körper liegt warm bei 288–299 ms (Median 292 ms) und
damit im Ziel. Dazu gibt der Kern seine Segmente bereits schichtweise aus, die
Verkettung braucht nur noch einen Sort, vorhandene Ein-Ring-Konturen werden
nicht aus GEOS zurückkopiert, und ein eindeutig schmales Überhangband wird
nicht ein zweites Mal als Brücke vermessen. Die Wandstärkenkarte verwendet
ihre zwei großen Abtastfelder wieder, statt sie in 175 Schritten neu anzulegen:
3,10 auf 1,43–1,48 s, mit bitgleich denselben 315 218 bekannten Werten. Der
Skizzenlöser begrenzt die inneren LSMR-Schritte so, dass TRF acht große statt
achtzehn übergenaue Versuche macht: 105 auf 48–50 ms, der Restfehler bleibt mit
1,3 × 10⁻⁹ weit unter der Kerntoleranz.

**Ein Zielwert steht mindestens die gemessene Streuung über dem Bestwert.**
Sonst misst er die Maschine. Der Anzeigeaufbau ist das Beispiel: 2,51 s
gemessen, Streuung dieser Maschine zwischen zwei Läufen 10 bis 31 Prozent —
ein Ziel von 3 s wäre unter Fremdlast rot geworden, ohne dass etwas langsamer
wurde. Also 4 s. Wird die Dezimierung eines Tages 3,5 s brauchen, fängt die
Zahl es noch; 2,5 auf 3,5 ist keine Streuung mehr.

**Und welche von zwei Zahlen gilt, entscheidet, wer sie liest — der Kunde die
kalte, der Wächter die warme.** Vor dem Umbau brauchte der Anwendungsstart beim
ersten Mal am Tag 12,9 s und danach 2,9; der Unterschied ist der Dateicache des
Betriebssystems. Die Suite kann nur den warmen messen, sie läuft mehrmals
täglich. Gemeint ist in §31 der **kalte** — dieser Plan schreibt über den
Kunden und nicht über die Suite. Am 29.08.2026 laden die 86
Operationsdeklarationen trimesh, scipy und networkx nicht mehr vor dem Fenster:
Register füllen 800 → 257 ms, vollständiger warmer Start 1,98 → 1,48 s. Der
erste wirkliche Rechenschritt lädt sie im sichtbaren, abbrechbaren Arbeitslauf.
Mit echtem OpenGL-Viewport statt der Offscreen-Messung steht der warme Start
bei 2,46 s und damit ebenfalls im Ziel.
Eine neue kalte Zahl braucht einen geleerten Betriebssystemcache und steht
deshalb ausdrücklich noch aus. Dieselbe Unterscheidung gilt für das Öffnen
eines Projekts: 5,06 s beim ersten Mal, 0,21 beim zweiten.

**Und die dritte Spalte ist nicht das, was das Tor prüft.** Die Zusicherungen
in `tests/test_performance.py` liegen bewusst eine Größenordnung über den
Zielwerten — die Schichtanalyse hält gegen 2,5 s, wo hier 300 ms stehen, der
Skizzen-Solver gegen 1 s statt 100 ms, die Erkennung gegen 10 s statt 1 s. Die
Kommentare dort sagen es selbst: „das Ziel ist ein Zehntel; eine Sekunde fängt
die Größenordnung". Das ist vertretbar, weil eine Zusicherung, die auf einer
fremden Maschine reißt, niemandem etwas über den Code sagt — aber es heißt:
**Ein grüner Leistungslauf belegt nicht, dass diese Tabelle eingehalten wird.**
Wer das wissen will, liest die Messwerte, nicht die Farbe.

**Zwei Qualitätsstufen**, im `OpContext` durchgereicht: **Entwurf** beim
Iterieren und in der Vorschau (gröbere Auflösung, Rückfallkette endet nach
Stufe 2, genäherte Analysekarten), **Fein** beim Export und im finalen
Prüfbericht. Der Agent arbeitet in Entwurfsqualität und schaltet erst beim
Abschluss um.

**Die Zielwerte gelten mit dem übersetzten Schichtkern.** Ohne ihn ist die
Schichtanalyse an der Decke des Interpreters, und das ist nicht vermutet,
sondern an drei Verfahren gemessen: Die Ringe selbst zu verketten statt sie
GEOS zu überlassen kostete in Python 1215 ms, vektorisiert 540 ms, GEOS selbst
1078 ms — dieselbe Größenordnung, obwohl GEOS mehr tut. Übersetzt sind es
11 ms. Der zweite Teil darin, die Ebenensegmente, fiel 203 auf 27–31 ms.
`slice/_chain` ist deshalb **Teil des ausgelieferten Pakets**. Suite und
Paketier-Job bauen ihn jeweils frisch für ihre Plattform; die PyInstaller-Spec
bricht mit einem Handlungsvorschlag ab, wenn er trotzdem fehlt, und nimmt die
Binärdatei ausdrücklich mit. Fehlt er in einem Quellklon, nimmt die Analyse den
NumPy-/GEOS-Weg und ist so schnell wie vorher — der Klon wird nicht langsamer,
nur nicht schneller. Und der Kern ist ausdrücklich **nicht der genauere Weg**:
Er rundet gleich; was er gewinnt, ist eine Ringschließung, die nicht davon
abhängt, dass zwei gerundete Enden zusammenfinden.

**Regressionsprüfung**: Messwerte je Lauf festhalten; Verschlechterung um mehr
als ein Viertel gilt als Fehler, nicht als Rauschen — **aber erst, wenn sie
zweimal hintereinander auftritt.** Ein einzelner Ausschlag ist Last, zwei sind
eine Richtung, und das kostet keinen zusätzlichen Lauf, weil der nächste ohnehin
kommt. Der Grund ist gemessen und unbequem: Zwei aufeinanderfolgende saubere
Läufe derselben Software auf derselben Maschine unter demselben Schloss lagen
zwischen 10 und 31 Prozent auseinander — die Streuung ist größer als die
Schwelle, und eine Schwelle unter der Streuung ist kein Wächter, sondern ein
Würfel. Die Regel automatisiert damit nur, was zwei Absätze weiter unten schon
steht: vorher ein zweites Mal messen.

Verglichen wird gegen den **besten** bisher gemessenen Wert **je Aufrufkontext**
— nicht gegen einen einzigen Bestwert für alle Läufe. Das ist die Entscheidung zwischen den zwei
möglichen Reparaturen, und sie fällt so, weil die andere den Vergleich fast
immer ausschaltete: Das Tor läuft geteilt, ein Prozess je Fensterdatei und
alles übrige in einem Zug, also sind „andere Testdateien im Lauf" der
Normalfall und nicht die Ausnahme. Ein Vergleich, der dann aussetzt, prüft
nichts mehr.

**Was ein roter Leistungstest bedeutet.** Zwei Schranken je Messung, und sie
sagen Verschiedenes: Der **absolute Zielwert** aus der Tabelle heißt „zu
langsam". Die **Regressionsschwelle** heißt „langsamer geworden" — vielleicht.
Am 22.08.2026 liefen auf derselben Maschine, am selben Tag, mit derselben
Software zwei Läufe: einer unter 48 % Fremdlast mit fünf roten Messungen, einer
unter 16 % mit neunzehn grünen. Alle fünf waren die Schwelle, keine ein
Zielwert; allein die Aufrufreihenfolge macht achtunddreißig Prozent. **Ein
roter Leistungslauf sagt zuerst etwas über die Maschine und erst danach über
den Code.** Wer eine Verschlechterung meldet, misst vorher ein zweites Mal auf
einer ruhigen Maschine. Ein roter Leistungstest allein heißt deshalb nicht
„nicht fertig" — als einziger roter Test in diesem Projekt.

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
- **Jedes externe Werkzeug läuft eingehegt**: fester Arbeitsordner je Aufruf,
  Zeit- und Speichergrenze, getrimmte Umgebung. Das gilt für die Übergabe an
  den Slicer (§28) wie für jedes weitere Programm, das der Kern startet (§27)
- **Warnhinweis beim Öffnen** einer fremden Datei mit externen Verweisen —
  nicht mehr, weil etwas laufen könnte, sondern damit der Nutzer weiß, woher
  der Inhalt stammt
- **Prüfsummen** aller Quellen beim Laden verifizieren
- **Grenzen beim Öffnen**: Dreieckszahl, Dateigröße **und die entpackte
  Größe** gedeckelt, mit klarer Meldung statt Speicherüberlauf. Die entpackte
  ist die, die man vergisst: Beim Import eines 3MF wurden aus 2,6 MB gepackt
  1,08 GB gelesen, und geprüft war nur die gepackte. Für die Projektdatei gilt
  dasselbe Maß — sie ist ebenfalls ein ZIP, und sie reist ausdrücklich zwischen
  Leuten (§16.2). Eine Grenze, die nur an einem von zwei Eingängen steht, ist
  die Lehre, die nur halb gezogen wurde
- **Eigene Bausteine (§24.5) reisen nie mit.** Ein Projekt verweist auf sie
  nur namentlich; fehlt der Baustein, hält die Auswertung an. Ausführbarer
  Code kommt ausschließlich aus der Installation und dem Nutzerverzeichnis,
  nie aus einer geöffneten Datei.

---

## 33. Fehler und Protokollierung

### 33.1 Ausnahmehierarchie
```python
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

Jede Ausnahme trägt `suggestions: list[Action]` — anklickbare Handlungen, keine
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
unter `tests/data/` und ist Teil des Repositorys.

Netze liegen unter `tests/data/meshes/`, Projektdateien unter
`tests/data/projects/`; erzeugt werden sie von `make_corpus.py`, das
mitversioniert ist.

| Datei | Zweck |
|---|---|
| `cube_clean.stl` | Grundfall: wasserdicht, 12 Dreiecke |
| `plate_holes.stl` | vier Bohrungen bekannter Größe — Feature-Erkennung, Messen |
| `plate_holes_twin.stl` | zwei identische Bohrungen dicht beieinander — Mehrdeutigkeit |
| `bracket_inch.stl` | in Zoll gespeichert — Einheitenerkennung |
| `plate_cm.stl` | in Zentimetern, Einheit mehrdeutig — die Rückfrage statt der Annahme |
| `broken_open.stl` | drei offene Stellen — Reparatur, Rückfallkette |
| `broken_selfint.stl` | Selbstdurchdringung — Rückfallstufen 3 und 4 |
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
| Bausteine | Parameterbereich vollständig, Vorschaubild erzeugbar |
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
Mehrdeutigkeit gefragt?

**Ein Test hinter einer Wache, die nie fällt, ist grün und prüft nichts.**
Dieselbe Zeile taucht in jeder Oberflächenprüfung wieder auf: Wo kein Bildpuffer
ist, überspringt der Test sich selbst — und deckt damit die Lücke zu, statt sie
offenzulassen. Die Antwort darauf ist nicht die nächste Attrappe. Sie ist,
**die prüfbare Aussage aus dem Unprüfbaren herauszulösen**: Was in einer Methode
entschieden wird, die anschließend zeichnet, ist eine Aussage über die Szene und
braucht kein Fenster, sobald es allein steht. Erst was danach übrig bleibt —
ein echter Picker, ein echter Puffer — verdient eine Attrappe.

Und eine Zahl bestandener Tests sagt nichts über die Tiefe: Ein Test, der eine
Methode ruft und an ihrer Wache umkehrt, zählt wie jeder andere. Wer wissen
will, was wirklich lief, misst Zeilen und nicht Läufe.

**Keine dieser Testarten fragt, ob etwas angeschlossen ist** — und der Fall, der
das gezeigt hat, kostete jedes Öffnen eines Projekts mehrere Sekunden. Der
Plattencache aus §38 war vollständig gebaut, vollständig geprüft und in der
Anwendung nie benutzt: Die Sitzung baute ihren Zwischenspeicher ohne die
Plattenebene, und der Name dieses Arguments kam in der ganzen Anwendung nicht
vor. Jeder Test darunter war grün, weil jeder sein Modul prüfte. **Der Fehler
saß nicht in einem Modul, sondern zwischen zwei**, und dort sieht die Tabelle
oben nicht hin. Die Hauptwege aus §2.2 sind die einzige Zeile, die es
grundsätzlich könnte — sie fahren die Kette von außen, und was sie nicht
berühren, prüft niemand von außen. Eine Zusage aus diesem Bauplan, die nur von
einer Stelle im Programm eingelöst wird, braucht einen Test an **dieser**
Stelle: nicht „der Cache kann es", sondern „die Anwendung tut es".

**Diese Zeile hat drei Bauarten, und keine davon ist ein Griff in den
Quelltext** — eine Suche nach dem Namen eines Arguments findet den Anschluss
auch dann, wenn er in einem toten Zweig steht.

* **Am echten Einstieg messen.** Der Test fährt den Weg, den die Anwendung
  fährt, und liest das Ergebnis dort ab, wo die Frage sitzt — nicht dort, wo
  die Funktion wohnt. Beim Plattencache heißt das: ein Projekt zweimal öffnen
  und feststellen, dass beim zweiten Mal nicht neu gerechnet wird.
* **Zwei Wege, eine Antwort.** Wo zwei Einstiege dieselbe Fähigkeit anbieten,
  prüft der Test sie **gegeneinander** und nicht gegen einen erwarteten Wert:
  dieselbe Eingabe, dieselbe Aussage. Gegen einen erwarteten Wert wäre er in
  beiden Wegen einzeln grün und übersähe genau den Fall, dass nur einer
  versorgt wurde (`detect()` gegen `detect_holes()`).
* **Ein einziger Aufrufer trägt den Test.** Hat eine Fähigkeit nur eine Stelle,
  an der sie eingelöst wird, gehört der Test an diese Stelle und nicht in das
  Modul, das die Fähigkeit anbietet.

Der Preis ist bekannt und wird bezahlt: Solche Tests fahren echte Wege und
sind teurer als die Modultests darunter. Die Gegenfrage am Ende dieses
Abschnitts entscheidet, wann sich das lohnt.

**Warum es eine Tabellenzeile ist und kein Absatz.** Alles oben stand hier
schon als Prosa, und es hat nichts verhindert: Ein Absatz wird gelesen und
genickt, eine Tabellenzeile wird abgehakt — aus dieser Tabelle zieht
`AGENTS.md` seine Testarten, und an ihr entlang prüft eine Sitzung, ob sie
fertig ist. Am 22.08.2026 traten an einem Tag **fünf** Fälle auf: der
Plattencache, `detect_holes()`, `parts/user.py::travelling_parts()` und
`parts/check.py::stamp()` — beide ohne jeden Aufrufer, die erste sogar mit
einem Docstring, der im Indikativ das Gegenteil behauptet. Der fünfte ist der
teuerste: `parts/user.py::load()` hatte denselben Fehler **schon einmal**,
gefunden und behoben. Ein Muster, das sich an einem Tag viermal wiederholt und
einmal an dieselbe Stelle zurückkehrt, ist keine Anekdote.

**Und ein Beispiel, das die Zeile nicht fordert, sondern vorführt:**
`tests/test_packaging.py` prüft kein Modul, sondern ob zwei getrennt gepflegte
Dinge noch zueinander passen — das gebaute Lizenzmanifest und die Grenzdateien
der Anwendung. Am 20.08.2026 fiel dieselbe Sache erst im Protokoll einer
Testinstallation auf; am 22.08. fing sie das Tor, Stunden nachdem zwei
Grenzdateien committet worden waren.

**Und eine Prüfung, die etwas Ähnliches prüft statt der Sache selbst, ist grün
aus dem falschen Grund.** Am 22.08.2026 dreimal aufgetreten, jedes Mal in
anderer Gestalt: Ein Wächter suchte den *Aufruf* statt der Funktion. Ein Test
setzte eine Änderungszeit *relativ* zu einer Datei, während gefragt war das
Maximum über ein ganzes Verzeichnis — er wurde rot, sobald irgendwer
irgendetwas anfasste, und grün, obwohl er nichts prüfte. Und `clear()` leerte
den *Speicher* statt den Cache, während sein einziger Aufrufer sich auf den
Namen verließ. Jedes Mal stand neben der Sache etwas, das ihr ähnlich sieht,
und die Prüfung griff danach.

**Und es trifft nicht nur Prüfungen, sondern auch Messungen.** Eine vierte
Fassung desselben Fehlers, am selben Tag: Um zu zählen, wie oft eine Prüfsumme
gerechnet wird, wurde die Funktion in dem Modul eingewickelt, in dem sie steht —
der Aufrufer hatte sie aber mit `from … import` geholt und hielt damit seine
eigene Referenz. Der Zähler blieb bei null, und die Auskunft wäre „passiert nie"
gewesen, obwohl es passierte. Wer messen will, wickelt dort ein, wo die Frage
sitzt, nicht dort, wo die Funktion wohnt.

Die Gegenfrage, die es findet, ist immer dieselbe: **Was müsste kaputt sein,
damit dieser Test rot wird — und ist das dasselbe wie das, wovor er schützen
soll?**

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
| PyVista / VTK | MIT / BSD | unkritisch |
| PySide6 | LGPL | geschlossene Weitergabe möglich, wenn dynamisch gebunden. **PyQt wäre GPL — nicht verwenden.** |
| keyring | MIT | der Schlüssel des Nutzers im System-Schlüsselbund (§27) |
| cadquery-ocp (OpenCascade) | Anbindung Apache-2.0, Kern LGPL-2.1 mit Linking-Ausnahme | wie PySide6 dynamisch gebunden |
| build123d / CadQuery | Apache-2.0 | unkritisch |
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

**Bei einer nativen Bibliothek entscheidet nicht die Lizenz.** Drei wurden am
14.08.2026 geprüft und alle drei an derselben Frage abgewiesen, ohne dass die
Lizenz je das Thema war: `pyclipr` (Clipper2, Boost) hat kein Linux-Rad,
`libigl` (MPL-2.0) liefert nicht für Windows und nur bis cp312, und CoACD wäre
gegangen. Die Regel daraus, und sie gehört in die Checkliste „neue
Abhängigkeit": Eine neue native Abhängigkeit braucht **Räder für Windows, macOS
und Linux in der Python-Version dieses Projekts.** Alles andere ist eine
Bauumgebung, die jemand pflegen muss — dann ersetzt die Bibliothek keine
Arbeit, sie verschiebt sie.

Damit ist auch das „prüfen" beantwortet, das hier bei CoACD stand: Auto Split
liest aus der Zerlegung eine einzige Zahl, die Stelle der Einschnürung, und
dort trifft V-HACD näher (Abweichung 7,2 gegen 9,2 an der Hantel). Genau
eingestellt ist CoACD zwei- bis fünfzigmal langsamer, grob eingestellt liefert
es ein Stück und damit gar keinen Hinweis. Es gibt keine Einstellung, in der es
gleichzeitig schnell und aussagekräftig ist.

**Eigene Lizenz vor der ersten Veröffentlichung festlegen** — rückwirkend
ändern geht nur mit Zustimmung aller Beitragenden. Vier Wege: GPL, Apache/MIT,
quelloffen-mit-Einschränkung, geschlossen.

**Die Bausteinbibliothek separat und freizügig lizenzieren** (MIT oder CC0) —
ihr Code landet in der Geometrie der Nutzer. Für den Testkorpus gilt dasselbe.

**Lizenzhinweise** im Über-Dialog. Eine Prüfung vergleicht die installierten
Abhängigkeiten gegen die Freigabeliste.

---

## 37. Veröffentlichung und Auflagen

### 37.1 Name
Wird für Paketnamen, Domain, Dateiendung, Übersetzungen und Signierung
gebraucht — früh entscheiden. Kriterien: als Paketname und Domain frei, keine
Markenkollision, in beiden Sprachen aussprechbar. Der Name steht an **einer**
Stelle im Code (`app/branding.py`), damit ein Wechsel eine Ein-Zeilen-Änderung
bleibt.

**Entschieden: „Solidon3D".** Der volle Name steht auf Fenstertitel, Website,
Installer und Lizenzschlüssel; im Fließtext und in Docstrings heißt es kurz
„Solidon". Die Begründung führt `konzepte/namensentscheidung-solidon.md`.

Hier stand bis zum 08.08.2026 zusätzlich „kein ‚3D' im Namen". Das Kriterium
war gegen einen beschreibenden Namen gerichtet und hat sich gegen zwei Dinge
nicht gehalten. Erstens die Marke: der Vorgänger „Formwerk" fiel, weil eine
Wort-/Bildmarke „3D FORMWERK" für „Entwurf von 3D-Modellen für den 3D-Druck"
bestandskräftig wurde — geprägt hat dabei *Formwerk*, das „3D" trat als
beschreibend zurück. Genau diese Beschreibungsschwäche macht das Kürzel als
Zusatz zu einem eigenen, kennzeichnungskräftigen Wortstamm unbedenklich.
Zweitens die Domain: `solidon3d.de` war frei, und Website, Support-Postfach,
Update-Datei und Fenstertitel sollen denselben Namen tragen — wer eine
Setup-Datei von der einen Adresse lädt und im Programm eine andere findet, hat
zwei Namen vor sich und keinen Grund zu glauben, dass sie zusammengehören.

Das Muster ist nicht neu: Shapr3D und Simplify3D führen dasselbe Kürzel. Es
kostet nichts, solange der Stamm allein trägt — und „Solidon baut keinen
G-Code-Slicer" liest sich besser als die Langfassung.

### 37.2 Auslieferung
- **Signierung.** Windows zuerst, Linux als AppImage oder Flatpak, macOS
  später (Beglaubigung nötig). Der bequeme Weg ist versperrt: Microsofts
  eigener Signierdienst nimmt nur Kunden in den USA und Kanada. Für eine
  deutsche Firma bleibt ein Zertifikat einer Zertifizierungsstelle mit
  Schlüssel in Hardware oder in einem Cloud-HSM — seit 2023 stellt niemand
  mehr einen Schlüssel als Datei aus, und ab dem 01.03.2026 läuft ein
  Zertifikat nur noch rund fünfzehn Monate. Das ist bei der CI mitzudenken:
  Der Bauläufer bekommt keinen Schlüssel, er bekommt einen Aufruf an einen
  Signierdienst.
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

  **Nicht überall geht es.** Flatpak und AppImage lassen sich nicht von innen
  ersetzen — dort bleibt es beim Hinweis und dem Weg zur Download-Seite. Auch
  wer aus den Quellen fährt, bekommt kein Paket angeboten.
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

Dieser Abschnitt hat gefehlt. Zwei europäische Rechtsakte betreffen eine
kommerziell verkaufte Desktop-Anwendung, und bei beiden ist die naheliegende
Vermutung die falsche: Der erwartete greift nicht, der unerwartete greift — mit
einer Frist drei Wochen nach dieser Durchsicht.

*Kein Rechtsrat, und der Bauplan wird keiner. Was hier steht, ist die
Aufgabenliste, die aus der Recherche folgt; bestätigen muss sie jemand mit
Zulassung, bevor ein Paket in den Verkehr geht.*

**Die Verordnung über Cyberresilienz (CRA, (EU) 2024/2847) greift.** Sie gilt
für „Produkte mit digitalen Elementen", die in der Union in Verkehr gebracht
werden, und Solidon ist eines: verkaufte Software mit Netzzugang für
Aktualisierung, Support und LLM. Die Ausnahme für freie und quelloffene
Software ohne Monetarisierung greift nicht — Solidon ist proprietär und kostet
Geld. Zwei Fristen:

| ab | was |
|---|---|
| **11.09.2026** | aktiv ausgenutzte Schwachstellen und schwere Zwischenfälle binnen 24 Stunden an ENISA und das nationale CSIRT melden |
| **11.12.2027** | die übrigen Pflichten: Anforderungen des Anhangs I, CE-Zeichen, EU-Konformitätserklärung, technische Dokumentation, maschinenlesbare Stückliste, Schwachstellenverfahren, Sicherheitsaktualisierungen über die erwartete Lebensdauer (mindestens fünf Jahre) |

Solidon fällt in die **Grundkategorie**, nicht in die Anhänge III oder IV, wo
eine benannte Stelle prüfen müsste. Die Konformitätsbewertung ist damit eine
**eigene**: Solidon erklärt sie selbst und trägt die Akten. Das ist die
günstige Variante — und trotzdem Arbeit.

Was dafür schon steht, ist mehr, als es aussieht, es ist nur nirgends als
Konformität aufgeschrieben: `constraints.txt` ist ein festgeschriebener
Versionssatz und damit die halbe Stückliste, `licences.toml` und
`THIRD-PARTY-NOTICES.md` sind die Aktenlage der Abhängigkeiten samt dem, was
extern läuft (§36), die Lizenzprüfung läuft im Tor, der Fehlerbericht sendet
nur auf Klick und zeigt vorher, was mitgeht (§37.2), das Protokoll bleibt
lokal (§33.2), es gibt genau einen Supportkanal, Parameterausdrücke laufen ohne
`eval`, fremde Dateien führen keinen Code aus (§32).

Was fehlt, und jedes für sich ist klein:

1. **Eine maschinenlesbare Stückliste** (CycloneDX oder SPDX), aus der
   Umgebung erzeugt, mitgeliefert und mitversioniert. Aus `constraints.txt` ist
   das ein Werkzeuglauf, kein Vorhaben — der Erzeuger für Python steht unter
   Apache-2.0 und ist damit nach §36 zulässig.
2. **Ein Schwachstellenverfahren mit Adresse**: wohin ein Finder meldet, wie
   lange die Antwort dauert, wie eine Behebung ausgeliefert wird. Der
   Supportkanal ist da, die Zusage fehlt.
3. **Eine erklärte Unterstützungsdauer**, sichtbar für den Käufer — nicht
   „solange es Spaß macht". Sie bindet: Was erklärt ist, muss bedient werden.
4. **Ein Weg, eine Meldung binnen 24 Stunden abzusetzen.** Das ist keine
   Software, sondern eine Handreichung: wer meldet, an wen, mit welchen
   Angaben. Ohne sie ist die Frist nicht einzuhalten, und sie gilt auch für ein
   Erzeugnis, das seit Jahren draußen ist.
5. **CE-Zeichen und Konformitätserklärung** zum Zeitpunkt des
   Inverkehrbringens, mit der technischen Dokumentation dahinter; für Klein-
   und Kleinstunternehmen in vereinfachter Form.

**Das Barrierefreiheitsstärkungsgesetz (BFSG) greift nicht** — und das ist die
Vermutung, die man prüfen muss, statt ihr zu folgen. Es gilt seit dem
28.06.2025, aber für eine aufgezählte Menge von *Produkten* (Hardware mit
Betriebssystem, Selbstbedienungsterminals, Lesegeräte, Telekommunikations- und
Mediengeräte) und eine aufgezählte Menge von *Dienstleistungen* (Telefonie,
Mediendienste, Personenverkehr, Bankdienste, E-Books, **elektronischer
Geschäftsverkehr**). Eine Anwendung, die man herunterlädt, ist keines der
genannten Produkte. Der Verkauf über die eigene Seite ist elektronischer
Geschäftsverkehr und damit eine genannte Dienstleistung — für die aber die
**Kleinstunternehmensausnahme** gilt: unter zehn Beschäftigte und höchstens
zwei Millionen Euro Umsatz oder Bilanzsumme. Beide Wege enden bei „nicht
anwendbar", der zweite allerdings nur, solange die Schwelle hält.

**Damit ist §19 eine Produktentscheidung und keine Pflicht** — und gilt
unverändert weiter. Das ist der bessere Grund: Blau/Orange statt Rot/Grün, die
zweite Kodierung neben jeder Farbe und die wahrnehmungsgleichen Paletten sind
gebaut, weil sie die Anwendung besser machen, nicht weil jemand sie verlangt.
Wer sie später kürzt, kürzt kein Zugeständnis an eine Behörde, sondern
Qualität.

**Der Chat ist als Chat erkennbar, und damit ist die Offenlegungspflicht der
KI-Verordnung für Systeme, die mit Menschen interagieren, erfüllt.** Solidon
ist Anwender eines Modells, nicht Anbieter eines; die Pflichten für Modelle mit
allgemeinem Verwendungszweck treffen den, der das Modell anbietet. Was Solidon
darüber hinaus tut, steht in §27 und §5: Wo eine Eingabe hingeht, ist gesagt,
und ohne Schlüssel geht sie nirgendwohin.

---

## 38. Desktop-Spezifika

- **Erstinbetriebnahme** beim ersten Start: Sprache und Druckerprofil wählen,
  die im Slicer eingelegten Filamente samt Typ und Farbe übernehmen, Pfade zu
  externen Programmen prüfen, LLM-Backend optional. Überspringbar und
  nachholbar.
- **Nebenläufigkeit.** Alles Rechnende im Worker-Thread mit Fortschritt und
  Abbrechen (§15.6).
- **Absturzwiederherstellung.** Der Autosave-Container liegt neben dem Projekt
  und wird beim nächsten Start angeboten.
- **Speicher und Cache.** Obergrenze im RAM, darunter ein Plattencache über den
  Op-Hash. Er liegt in **seinem eigenen Ordner**, und zwar aus zwei Gründen, die
  beide beim Anschließen scharf wurden. Der erste ist die Nachbarschaft: Im
  Cache-Verzeichnis wohnen auch die Arbeitsordner der externen Werkzeuge
  (§32), geladene Aktualisierungspakete (§37.2) und die Oberflächenvorlagen.
  Ein Aufräumen, das sein Budget über den ganzen Ordner rechnet, zählt fremde
  Daten mit und löscht
  fremde Dateien — darunter ein Paket, dessen Prüfsumme gerade geprüft werden
  soll. Der zweite ist die **Versionsschranke**: Der Op-Hash trägt Operation,
  Parameter, Eingänge, Profil, Qualität und Startwert — er ändert sich **nicht**,
  wenn die Umsetzung einer Operation sich ändert. Im Speicher ist das gleichgültig,
  der Cache lebt eine Sitzung; auf der Platte überlebt ein Eintrag die
  Installation der nächsten Fassung und liefert ein Netz, das alter Code gerechnet
  hat — eine behobene Rückfallstufe wäre damit stillschweigend ausgehebelt.
  Deshalb steht die Fassung im **Ordnerpfad** und nicht im Schlüssel: Ein Update
  fängt kalt an, und die Ordner der Vorfassungen werden dabei weggeräumt.
  Dieselbe Schranke braucht den Zustand der eigenen Bausteine (§24.4), denn ein
  geändertes Maß darin bewegt den Hash ebenfalls nicht.

  **Der Schlüssel muss decken, wovon das Ergebnis abhängt — vollständig und
  trotzdem umsonst.** Ein Quellparameter trägt einen Bezeichner, `src_1`, und
  jedes Projekt nennt seine erste Quelle so; zwei völlig verschiedene Dateien
  hatten damit denselben Schlüssel, und ein Projekt bekam die Geometrie eines
  anderen. Also steht dort die Inhaltsprüfsumme. Dasselbe gilt für den Stand der
  eigenen Bausteine (§24.4) und für die Fassung der Anwendung: Wo eine Größe das
  Ergebnis ändert, ohne im Schlüssel zu stehen, ist ein Cache kein
  Zwischenspeicher, sondern eine Verwechslung.

  Dass die Inhaltsprüfsumme nichts kostet, liegt an einer zweiten Zusage: Jede
  Quelle kennt ihren Inhalt **von ihrer Entstehung an**, nicht erst vom
  Speichern. Gemessen in der laufenden Anwendung: zwei Nachfragen nach der
  Kennung, beide auf dem schnellen Weg, null gerechnet. Gerechnet wird nur bei
  einer verknüpften Quelle ohne Prüfsumme — die gibt es in der Anwendung heute
  nicht, und sie muss jedes Mal neu gelesen werden, weil eine Datei draußen sich
  zwischen zwei Auswertungen geändert haben kann.

  **Und daraus folgt eine Regel, die über den Cache hinausgeht:** Eine
  Cache-Ebene, die länger lebt als eine Sitzung, ist keine Erweiterung, sondern
  ein **Prüfstand für die Schlüssel**. Der Speichercache wird beim Öffnen eines
  Projekts geleert und lebt eine Sitzung — er verzeiht jeden zu kurzen Schlüssel,
  und drei Fehler dieser Art lagen unter ihm, ohne dass ein Test anschlug. Wer
  eine Ebene mit längerem Leben anhängt, prüft damit nicht den Cache, sondern
  jede Annahme darüber, wovon ein Ergebnis abhängt.

  Gemessen ist der Gewinn und die Reihenfolge, in der man ihn liest: Ein Projekt
  mit einem 1,3-Mio.-Dreieck-Körper öffnet beim ersten Mal in 5063 ms und beim
  zweiten in **209**. Ein Cache bleibt dabei eine Beschleunigung und keine
  Voraussetzung — lässt sich der Ordner nicht anlegen, arbeitet die Sitzung mit
  dem Speicher allein weiter, ohne Dialog. Und er speichert nur, was eine
  **reine Funktion des Dokuments** ist (§15.1): Solange eine Antwort auf
  `ctx.ask` nicht im Stapel steht (§15.7), ist das Ergebnis keine, und es gehört
  nicht auf die Platte.
- **Zugangsdaten** im System-Schlüsselbund.
- **Profile**: Bauraum, Düse, Schichthöhe, Materialtoleranzen — nie fest im
  Code. **Ein Startsatz gängiger Druckerprofile wird mitgeliefert**, damit
  beim ersten Start niemand Bauraummaße abtippt; eigene Profile werden davon
  abgeleitet. Der Startsatz ist eine Datentabelle wie die Normteile (§24.2)
  und wird genauso gepflegt.
- **Paketierung.** PyInstaller. ComfyUI, Ollama und Slicer werden
  nicht mitgeliefert, sondern konfiguriert — mit Prüfung beim Start und klarer
  Meldung, wenn eines fehlt.

---

## 39. Die Regelsammlung

Laut Plan das eigentliche Produkt — also wird sie wie eines behandelt: eigene
Dateien unter `core/knowledge/rules/`, mit Version und Änderungsverlauf. Jede
Änderung mit Datum, Anlass und Suite-Ergebnis vorher/nachher. Verschlechtert
sich die Quote, wird die Regel zurückgenommen oder umformuliert. Der
Systemprompt referenziert die Version; jede Transaktion hält sie fest (§26.4).

Was sich als Baustein fassen lässt, wandert aus der Sammlung in die Bibliothek.
Eine eingehaltene Regel ist besser als eine beschriebene.

Aktueller Stand:

- Mindestwandstärke = 2 × Extrusionsbreite, nie darunter
- Fasen statt Überhängen über 45°
- Passungstoleranzen aus dem kalibrierten Materialprofil, nie als feste Zahl
- Hauptabmessungen als Projektparameter, nicht als Streuzahlen
- Bei Booleschen Ops immer 0,01 mm Überlappung, nie koinzidente Flächen
- Löcher größer als Nennmaß, weil FDM enger druckt — Wert aus der Kalibrierung
- Erste Schicht: Elefantenfuß einkalkulieren

---

## 40. Phasen mit Abnahmekriterien

Die Arbeitsliste je Phase steht in `ROADMAP.md`. Hier stehen Umfang,
Zielmodule und Abnahme.

**Diese Liste ist nicht die Arbeitsliste, und sie ist auch nicht der Stand.**
Sie nennt, was eine Phase umfasst und woran sie als fertig gilt; was offen ist,
steht im Register von `ROADMAP.md` und nirgends sonst. Bis zu dieser Fassung
endete sie bei P13, während P14 bis P16 gebaut und abgenommen waren — ein Plan,
der ein Drittel der geleisteten Arbeit nicht kennt, wird beim nächsten Abgleich
als Widerspruch gelesen, und dann sucht jemand einen halben Tag nach einem
Fehler, der keiner ist.

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
drei Schemata · Leistungsziele Viewport erreicht.

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
*Module:* `core/perceive`, `core/slice`, `ui/overlay`, `ui/report`,
`ui/layerview`

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

### P12 — B-Rep-Kern
*Fertig, wenn:* Verrundung an einer Referenzkante geometrisch exakt · STEP
rundreisefähig · Kennzeichnung Mesh/B-Rep korrekt.

### P13 — Skizzen und tiefere Konstruktion
*Module:* `core/sketch` (Datenmodell, Solver), `core/brep`
(Formgebungs-Ops), `ui/sketch` (Editor)

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

Die erste Veröffentlichung wartet auf diese Phase (Entscheidung vom
31.07.2026): der Launch führt die Skizzen als Kernargument. Die
Veröffentlichungsreste aus P8 laufen parallel.

### P14 — Die Oberfläche einlösen
*Module:* `ui` durchgehend, `scene/history`, `agent/apply`

Achtundzwanzig Funde aus der Durchsicht der gesamten Bedienung, mit fünf
Ursachen — wer die fünf behebt, behebt die achtundzwanzig. Die schwerste:
**Das Dokument kannte nur Operationen.** Parameter, Passungen, Drucker und
Material standen außerhalb von Transaktion und Undo, und damit war Regel 16
für alles verletzt, was keine Op ist. Ein Wert in der Parameterleiste ging
direkt ins Dokument: kein Undo, kein Stern im Titel, beim Schließen weg.

*Fertig, wenn:* jede Änderung am Dokument geht durch eine Transaktion, auch
wenn sie keine Operation enthält · ein Strg+Z nach einem angenommenen Vorschlag
nimmt dessen Parameter und Passungen mit zurück · jede ungespeicherte Änderung
steht im Titel · die Tests nehmen den Weg, den ein Mensch nimmt, und nicht den
kurzen daneben — ein Test, der die Rücknahme direkt aufruft statt über die
Oberfläche, deckt genau diesen Fund zu.

### P15 — Konstruieren und zeigen
*Module:* `ui/sketch`, `ui/viewport`, `geom/texture_ops`, `geom/lattice`,
`geom/pattern_ops`, `ui/remote_server`, `agent/remote`

Zweiundzwanzig Lücken gegen das Wettbewerbsfeld, vier davon begründet
abgelehnt. Solidon lag bei Druckintelligenz und Dokumentlogik vorn, bei
Konstruktionswerkzeugen, Bediensprache und Darstellung zurück.

**Die Grenzen kamen zuerst, nicht zuletzt**: höchstens neun Menüs, zwölf Zeilen
je Menü, acht Umschalter, acht Felder auf der Vorderseite eines Dialogs, genau
eine sichtbare Handlung genau einmal; technisch gleichwertige Zwillinge und
Varianten teilen ihren Einstieg. Vor dem Wachstum eingezogen ist das ein Riegel;
danach eingezogen wäre es eine Bestandsaufnahme. Der erste Lauf fand sofort ein
Menü mit 23 Zeilen.

*Fertig, wenn:* die Obergrenzen sind Tests und grün · der Skizzenmodus arbeitet
ohne Dialog auf einer angeklickten Fläche · Texturen sind echte Geometrie, flach
und umlaufend · die Fernsteuerung nach §26.6 läuft mit allen fünf Auflagen · was
begründet nicht gebaut wurde, steht mit seinem Grund im Konzept und nicht als
Lücke da.

### P16 — Organische Modellierung
*Module:* `geom/sculpt`, `geom/pose`, `geom/blend`, `ui/sculpt`

Weg 4 aus §2.2. Der Kundenkreis ist erweitert (Entscheidung vom 13.08.2026):
Figuren gehören dazu, Posing wird mitgenommen.

**Regel 2 war nie das Hindernis.** Sie verbietet Geometrieänderungen außerhalb
einer Op und verlangt nirgends, dass jede Nutzergeste ein eigener Schritt wird
— diese Gleichsetzung stand nur in der Auslegung, und der Skizzeneditor aus P13
hatte sie längst gebrochen. Regel 2 und §2.2 sagen das seither ausdrücklich.

**Die Messung hat den Entwurf entschieden, nicht umgekehrt.** Ein Pinselstrich
je Durchgang kostet bei 100 Strichen auf 16 000 Vertices schon 747 ms und wächst
mit dem Produkt aus Strichzahl und Vertexzahl; alle Striche in einem Durchgang
über einen KD-Baum schaffen 5 000 Striche auf 65 538 Vertices in 586 ms. Faktor
sechzig, und er entscheidet zwischen „geht nicht" und „geht". Der Preis steht
als Entscheidung im Konzept: Striche werden dadurch kommutativ, und Werkzeuge,
bei denen das nicht trägt, laufen in Etappen.

*Fertig, wenn:* ein Editor sammelt beliebig viele Gesten in einen Parameterwert,
und das Ergebnis entsteht erst bei der Auswertung · fünftausend Striche bleiben
im Leistungsziel · **Weg 4 aus §2.2 läuft als Ende-zu-Ende-Test** · das
Beispielprojekt liegt bei und das Handbuch hat sein Kapitel.

---

## 41. Ausbaustufen

**Vorlagenbibliothek.** Projekte ohne Quellen, nur mit Parametern und
Bausteinen, sind bereits Vorlagen (§13) — es fehlt nur die Verwaltung.

**Verzweigungen im Stack.** Mehrere Varianten nebeneinander statt Verwerfen.

**Fallbibliothek.** Erfolgreiche Paare aus Anfrage und Transaktion speichern
und bei ähnlichen Anfragen mitgeben. **Die Anfragen der Testsuite dürfen nie
hineinwandern**, sonst misst man nur das eigene Gedächtnis. Strikt lokal.

**Stapelverarbeitung** über den Kommandozeilen-Einstieg.

**Der Radius einer Verrundung.** Kugel und Torus sind seit dem 22.08.2026 in
der Erkennung (§21.1) — beide über denselben Weg, den der Kegel gezeigt hat:
Die Grundform kommt aus den Normalen, linear und ohne Zufall. Der
vorhergesagte Preis ist dabei eingetreten und wurde bezahlt: Eine Senkung
passt gut genug auf eine Kugel, um sie zu verlieren, und die Antwort waren
eine strengere Schwelle und eine feste Reihenfolge der Prüfungen.

Was bleibt, ist das Torus**stück**. Die Einpassung liest beide Radien aus den
Rändern eines Flecks und braucht dafür einen ganzen Ring; eine Verrundung ist
aber ein Ausschnitt. Damit fehlt weiter **der Radius einer Verrundung**, also
die Karte „Krümmung" aus §18.4 mit echten Zahlen statt einer Einfärbung. Eigene
Abnahme, eigene Testkörper, dieselbe Auflage wie überall: Was unter der
Schwelle bleibt, wird als Cluster gemeldet und nicht geraten (Regel 21).

**Modell-Vergleich.** Zwei Versionen überlagern, Unterschiede zeigen.

**Druckerhistorie.** Was wurde wann mit welchen Einstellungen gedruckt, mit
Ergebnisnotiz. Speist die Regelsammlung.

**Bewusst nicht:** Web-Anwendung im Browser, Mehrbenutzerbetrieb, Cloud-Ablage
von Projekten, Plugin-System, Telemetrie, eigener G-Code-Slicer.

Zur Abgrenzung: Eigene Bausteine (§24.5) sind **kein** Plugin-System. Sie
erweitern die Bibliothek, nicht die Anwendung, gelten nur lokal und reisen nie
mit einer Projektdatei.

---

## 42. Grenzen, die bleiben

- Generierte Meshes sind maßlich unpräzise; für Passungen taugen sie nicht
- Strukturen unter etwa 1 mm Wandstärke bleiben fragil
- Ein importiertes Mesh hat keine Konstruktionshistorie — was aus einem STL
  nicht erkennbar ist, kann auch die beste Feature-Erkennung nicht
  rekonstruieren (bei STEP anders, §30)
- Rückfallstufe „voxel" rettet die Operation, kostet aber Genauigkeit
- Reproduzierbarkeit gilt nur bei gleichen Bibliotheksversionen
- Farbquantisierung aus Texturen bleibt gröber als das Rendering
- Verrundungen auf Mesh-Kanten bleiben ein Kompromiss bis zum B-Rep-Kern
- Baugruppen mit echten Funktionstoleranzen bleiben Handarbeit; der Agent
  liefert den Entwurf, nicht das Endergebnis
- Die Zielwerte in §31 gelten mit dem übersetzten Schichtkern; ohne ihn ist die
  Schichtanalyse an der Decke des Interpreters, und das ist an drei Verfahren
  gemessen und nicht geschätzt
- Aus einem Netz erkennt die Wahrnehmung Zylinder, Kegel, Kugeln, Tori und
  Ebenen (§21.1, `DETECTABLE_KINDS`), aber **kein Torusstück** — und damit hat
  eine Verrundung weiter keinen Radius. Kegel, Kugel und Torus kamen am
  22.08.2026 dazu; seither ist eine Senkung nicht mehr nur ein zweites Merkmal
  neben der Bohrung, sondern geht in sie ein: Ob ein gesenktes Loch durchgeht,
  rechnet `_is_through` aus beiden zusammen
  (`test_a_countersunk_bore_is_still_a_through_hole`)

---

## 43. Nächster Schritt

Hier stand bis zu dieser Fassung die Aufbauliste von P0, elf Punkte, beginnend
mit „Paketstruktur mit Importtest". P0 bis P16 sind gebaut und abgenommen; das
war die letzte Stelle, an der der Bauplan zwei Jahre zu früh stand.

**Der nächste Schritt ist keine Phase, sondern ein Datum.** Am 11.09.2026
beginnt die Meldepflicht aus §37.3 — die einzige offene Sache mit einer Frist,
die nicht dieses Projekt setzt. Davor gehören erledigt: die maschinenlesbare
Stückliste, die Meldeanschrift samt Verfahren, die erklärte
Unterstützungsdauer. Das sind Tage, nicht Wochen — aber sie fangen nicht von
selbst an.

**Danach in dieser Reihenfolge:**

1. Die Reste von P8, die die erste Veröffentlichung tragen: Zertifikat
   (§37.2), CI-Bauläufe und DMARC; das Support-Postfach ist eingerichtet
2. Die Entscheidungen dieser Fassung in Code überführen — §15.7 (die Antwort
   gehört in die Parameter), §31 (Bestwert je Aufrufkontext, übersetzter Kern
   im Paket), §28.2 (Kandidaten aus der konvexen Hülle), §37.2 (Unterschrift
   über die Versionsdatei)
3. Was im Register von `ROADMAP.md` darüber hinaus steht, von oben nach unten

Regeln in `AGENTS.md`, Arbeitsliste in `ROADMAP.md`. **Offene Arbeit steht dort
und nirgends sonst** — auch nicht hier: Was in diesem Abschnitt steht, ist eine
Reihenfolge, kein Bestand.
