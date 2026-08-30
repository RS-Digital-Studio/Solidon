# Konzept — technische Produktreife: KI, Bibliotheken und Updates

> **Stand 30.08.2026 · Recherche- und Entscheidungskonzept.** Dieses Dokument
> erteilt keinen Auftrag und verändert weder Roadmap noch Bauplan. Es ergänzt
> die übergreifende Produktrichtung des Produktkompasses: Dieser beschreibt das
> gewünschte Kundenerlebnis, dieses Dokument erklärt die technische Linie, mit
> der es zuverlässig, schnell und dauerhaft hochwertig werden kann.

Bezug: Bauplan §2, §9, §15, §23, §26, §31, §35, §36, §38, §39 und §42 sowie
[`konzept-agent-vertiefung.md`](konzept-agent-vertiefung.md) und
[`konzept-versionspflege-2026-08.md`](konzept-versionspflege-2026-08.md).

---

## 1. Zielbild

Solidon soll sich für einen Menschen ohne CAD-Erfahrung nicht wie ein
vereinfachtes CAD anfühlen. Es soll sich wie ein verlässlicher Begleiter vom
Modell bis zum Slicer verhalten:

```text
Datei oder Idee
      ↓
Solidon versteht den Zustand
      ↓
Solidon zeigt die nächste sinnvolle Handlung
      ↓
Änderung mit Vorschau und einem Undo
      ↓
verständliche Prüfung und sichere Übergabe
```

Der Kunde muss dabei keine technische Betriebsart wählen und keinen
Geometriebegriff kennen. Mehr Tiefe bleibt erreichbar, erscheint aber erst,
wenn sie gebraucht wird. Ohne eingerichtete KI bleibt der gesamte Weg außer
dem Chat benutzbar.

Die technische Leitentscheidung lautet deshalb:

> **Nicht mehr Technik an die Oberfläche bringen, sondern die vorhandene
> Technik zu einem einheitlichen, messbar zuverlässigen Produkterlebnis
> verbinden.**

## 2. Klare Entscheidungen des Konzepts

| Bereich | Entscheidung | Begründung |
|---|---|---|
| Bedienung | Bestehenden Fensteraufbau veredeln, keinen Einfach-/Profi-Modus und keinen weiteren Hauptbereich einführen | Anfänger und erfahrene Nutzer arbeiten dann am selben Projektzustand und lernen dieselbe Bedienlogik. |
| Gestaltung | Ein eigenes kleines Gestaltungssystem auf dem vorhandenen Qt-Widgets-Unterbau verwenden | Solidon braucht eine erkennbare, ruhige Produktsprache statt eines fremden Themes. |
| Leistung | Reaktionszeit und verständliche Rückmeldung als Teil jeder Funktion behandeln | Eine schöne Oberfläche wirkt nicht hochwertig, wenn sie während einer Berechnung einfriert oder unklar wartet. |
| KI | Zuerst den sehr großen Agentenauftrag verkleinern und die Qualität messen | Der heutige Prompt ist der nachgewiesene Engpass; ein bloßer Modellwechsel löst ihn nicht. |
| Bibliotheken | Keine neue allgemeine Laufzeitbibliothek einführen | Geometrie, Oberfläche und Dateiformate sind bereits durch einen modernen Bestand abgedeckt. |
| Qualitätssicherung | Wenige Entwicklungs- und Bauwerkzeuge gezielt prüfen | Sie dürfen Fehler verhindern, ohne beim Kunden neue Abhängigkeiten oder Bedienkomplexität zu erzeugen. |
| Updates | Nur einen nachweislich grünen Versionssatz ausliefern | „Neueste Version“ ist kein Qualitätsmerkmal, wenn sie Geometrie, Paketbau oder Oberfläche verändert. |

## 3. Ausgangspunkt: Was bereits gut ist und wo der echte Hebel liegt

### 3.1 Der technische Unterbau ist bereits modern

Solidon nutzt am Stichtag unter anderem PySide6/Qt 6, PyVista/VTK,
manifold3d, trimesh 5, NumPy, SciPy und OpenCASCADE. `constraints.txt` hält
einen geprüften Versionssatz fest; ein wöchentlicher CI-Lauf prüft zusätzlich
neu auflösbare Versionen. Ein großer Bibliothekswechsel würde deshalb viel
Risiko erzeugen, ohne ein belegtes Kundenproblem zu lösen.

Das gilt besonders für die Oberfläche. Ein Wechsel auf Qt Quick/QML würde
Widgets, VTK-Anbindung, Tastaturwege und Tests zunächst verdoppeln. Modernität
entsteht hier sinnvoller durch konsequente Abstände, Typografie, Zustände,
Fokus, Bewegung und Rückmeldung im vorhandenen System.

### 3.2 Der lokale Agent trägt zu viel Werkzeugbeschreibung

Nach dem Laden aller Operationen besitzt der Agent am Stichtag **106
Werkzeuge**. Neu gemessen:

| Werkzeugsatz | Größe |
|---|---:|
| vollständige Beschreibungen | 146.025 Byte |
| bereits gekürzter Ollama-Satz | 106.724 Byte |
| bisherige Ersparnis | 26,9 % |

Der echte Ollama-Auftrag umfasst trotz Kürzung **23.891 Eingabe-Token** bei
einem eingestellten Kontextfenster von 32.768 Token. Fast drei Viertel des
Fensters sind damit belegt, bevor Szene, Verlauf, Auswahl, Nutzerfrage und
Zwischenergebnisse hinzukommen.

Auf einer bereits gemessenen Maschine ohne nutzbare Ollama-Grafikbeschleunigung
braucht allein das Einlesen dieses Auftrags ungefähr 51 Minuten. Damit ist
nicht die Formulierung im Chat der größte KI-Hebel, sondern die Größe dessen,
was vor jeder Antwort wieder gelesen werden muss.

## 4. Das Qualitätssystem für die ganze Anwendung

Der Produktkompass beschreibt „Öffnen → Verstehen → Verbessern → Prüfen →
Übergeben“. Damit dieser Weg überall gleich gut funktioniert, gelten vier
Verträge.

### 4.1 Versprechensvertrag: Die Website muss im Produkt wiederzufinden sein

Jedes konkrete Website-Versprechen braucht einen vollständigen Kundennachweis.
Nicht „die Funktion existiert“ zählt, sondern „der Kunde erreicht das
versprochene Ergebnis“:

- Eine Datei ablegen und sofort verstehen, was geöffnet wurde.
- Einen Befund anklicken, seine Folge verstehen und zum Ort im Modell kommen.
- Eine Fläche oder ein erkanntes Merkmal ohne CAD-Neukonstruktion ändern.
- Eine Passung aus Drucker- und Materialprofil ableiten, ohne Toleranzen zu
  raten.
- Eine geprüfte Datei mit Einheit, Objektzahl und verbleibenden Risiken an den
  vorhandenen Slicer übergeben.
- Alle diese Wege ohne Chat durchführen.

Dieser Vertrag ist zugleich ein Produktfilter: Eine neue Idee ist wichtig,
wenn sie einen dieser Wege klarer, schneller oder sicherer macht. Eine
Funktion ohne Verbindung zu einem Kundenweg braucht eine besonders starke
Begründung.

### 4.2 Interaktionsvertrag: Eine Absicht hat überall denselben Ablauf

Menü, Kontextmenü, Befehlssuche, Prüfbericht und Chat bleiben verschiedene
Einstiege in dieselbe Operation:

```text
Auswahl → verständliche Handlung → Hauptwerte → Vorschau → Übernehmen
                                                        ↓
                                                 ein vollständiges Undo
```

Das verhindert parallele „einfache“ Sonderwege. Der Chat bekommt keine
Sondermacht, der Viewport ändert keine Geometrie außerhalb einer Operation,
und eine automatische Vorbereitung bleibt ein erklärbarer Vorschlag aus
registrierten Operationen.

### 4.3 Gestaltungsvertrag: Ruhige Hierarchie statt Dekoration

Ein kleines, zentrales Gestaltungssystem definiert:

- Abstände, Zeilen- und Feldhöhen;
- Typografie und Zahlenanordnung;
- Auswahl, Fokus, Warnung, Fehler und Erfolg;
- Piktogramme und zugehörige Wörter;
- Bewegung, Vorschau und Kamerafahrt;
- helle und dunkle Darstellung.

Die 3D-Ansicht bleibt visuell am wichtigsten. Markenfarbe kennzeichnet nicht
gleichzeitig normalen Rahmen, Auswahl, Warnung und primäre Handlung. Kein
Zustand hängt allein von Farbe ab.

Qt 6 unterstützt High DPI grundsätzlich, der eigene OpenGL-/VTK-Weg muss den
Gerätefaktor jedoch korrekt mitführen. Deshalb gehören unterschiedliche
Skalierungen und Monitorwechsel in die visuelle Prüfung. [Qt: High
DPI](https://doc.qt.io/qt-6/highdpi.html)

Qt-Standardwidgets besitzen bereits Zugänglichkeitsrollen. Eigene Griffe,
Viewport-Markierungen und Spezialfelder benötigen ebenso Name, Rolle, Zustand
und Ereignisse. [Qt: Zugänglichkeit von
QWidget-Anwendungen](https://doc.qt.io/qt-6/accessible-qwidget.html)

Als Qualitätsmaßstab passen die WCAG-2.2-Muster: sichtbarer und nicht
verdeckter Fokus, ausreichend große Ziele, eine Alternative zu Ziehgesten und
Hilfe an einem beständigen Ort. [W3C: WCAG
2.2](https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/)

### 4.4 Leistungs- und Rückmeldungsvertrag: Warten muss verständlich bleiben

Die Leistungsbudgets aus Bauplan §31 bleiben verbindlich. Zusätzlich gilt bei
jeder längeren Handlung:

- Sofort wird sichtbar, dass Solidon reagiert hat.
- Der aktuelle fachliche Schritt wird benannt.
- Eine neue Eingabe ersetzt veraltete Vorschauarbeit.
- Abbrechen beendet auch die zugehörige Warteschlange.
- Vorschau rechnet grob, die Übernahme fein — beide über dieselbe Operation.
- Prozentwerte erscheinen nur, wenn ein echter Gesamtumfang bekannt ist.
- Eine langsame, aber laufende Rechnung wird anders erklärt als ein Fehler.

So entsteht wahrgenommene Qualität ohne künstliche Animation oder
unbegründete Fortschrittsanzeigen.

## 5. KI-Konzept: hilfreich, schnell und streng begrenzt

### 5.1 Was die KI leisten soll

Die KI übersetzt Alltagssprache in die vorhandenen Solidon-Werkzeuge. Sie
hilft beim Finden, Erklären und Zusammenstellen von Operationen. Sie erzeugt
keine Geometrie selbst, führt keinen Quelltext aus und umgeht keine Vorschau.

Der sichere Ablauf bleibt:

```text
Nutzerwunsch
    ↓
Modell schlägt registrierte Werkzeuge und Werte vor
    ↓
Solidon prüft Namen, Objekte, Werte, Grenzen und Mehrdeutigkeit
    ↓
vollständige Vorschau für den Nutzer
    ↓
Übernahme als genau eine Transaction
```

### 5.2 Erste KI-Priorität: Wiederholungen aus dem Auftrag entfernen

Der Systemprompt soll ein kurzer Produktvertrag sein, keine Kopie des
Handbuchs. Statische Inhalte stehen zuerst, wechselnde Inhalte zuletzt:

1. Sicherheits- und Bedienvertrag;
2. Werkzeugzugang;
3. Szene, Auswahl und Verlauf;
4. aktuelle Nutzerfrage.

Regeln stehen nur einmal. Werkzeugtexte erklären knapp Zweck,
Einsatzzeitpunkt, Eingaben, Nebenwirkungen und Fehlerweg. Ausführliche Hilfe
und Menüpfade bleiben auffindbar, müssen aber nicht bei jeder lokalen
Geometrieanfrage vollständig mitreisen.

Dieses Muster folgt auch der offiziellen Empfehlung, Prompts klein zu halten,
statische Präfixe zu cachen und Modelländerungen gegen repräsentative Evals zu
prüfen. [Offizielle OpenAI-Dokumentation zur
Modelloptimierung](https://developers.openai.com/api/docs/guides/latest-model)

### 5.3 Zweite KI-Priorität: Werkzeugentdeckung prüfen, ohne Werkzeuge zu verstecken

Die nächste sinnvolle Untersuchung ist ein zweistufiger Werkzeugkatalog:

1. Das Modell sucht mit einem kleinen Werkzeug nach einer passenden
   Solidon-Operation.
2. Es erhält dafür das genaue Parameterschema und ruft anschließend genau
   diese registrierte Operation auf.

Dadurch müssten nicht mehr 106 vollständige Schemas vor jeder Antwort
mitreisen. Trotzdem bleibt jede Operation erreichbar. Es entsteht kein
verdeckter Einfachmodus und kein Auswahlfilter, der eine unerwartete, aber
richtige Operation unauffindbar macht.

Diese Änderung ist ausdrücklich ein **Messkandidat**, keine Vorentscheidung.
Sie ist nur besser, wenn sie einschließlich des zusätzlichen Suchschritts:

- weniger Eingabe-Token benötigt;
- schneller zur ersten brauchbaren Rückmeldung kommt;
- die Trefferquote der Agenten-Suite mindestens hält;
- keine Operation unerreichbar macht;
- nicht mehr ungültige oder erfundene Aufrufe erzeugt;
- bei Mehrdeutigkeit weiterhin fragt statt zu raten.

Wenn der Gesamtwert nicht besser wird, bleibt der heutige Werkzeugsatz.

### 5.4 Strukturierte Ausgaben helfen, die eigene Prüfung bleibt maßgeblich

OpenAI Responses und Ollama unterstützen strukturierte Ausgaben nach Schema;
beide können Werkzeugaufrufe maschinenlesbar übertragen. [OpenAI Responses
API](https://developers.openai.com/api/reference/cli/resources/responses/methods/create),
[Ollama: Structured
Outputs](https://docs.ollama.com/capabilities/structured-outputs)

Das reduziert Transportfehler, ersetzt aber keine Solidon-Regel. Jeder Aufruf
wird weiterhin gegen Op-Register, Objekte, Parametergrenzen und
Sicherheitsvertrag geprüft. Ein fehlerhafter Wert wird nicht stillschweigend
„passend geraten“.

### 5.5 Streaming ist Rückmeldung, keine vorzeitige Ausführung

Ollama kann inzwischen auch Werkzeugaufrufe streamen. [Ollama: Tool Calling
und Streaming](https://docs.ollama.com/capabilities/tool-calling) Für Solidon
ist das nur sinnvoll, wenn:

- der Kunde verständliche Arbeitsphasen statt eines Gedankentagebuchs sieht;
- Text und Werkzeugaufrufe vollständig gesammelt werden;
- kein Teilaufruf ausgeführt wird;
- danach dieselbe Validierung wie ohne Streaming läuft;
- Abbrechen kein Dokument verändert.

Streaming kann das Warten verständlicher machen. Es darf die
Transaktionsgrenze nicht verändern.

### 5.6 Lokales Bildverständnis bleibt eine geprüfte Zugabe

Ollama meldet Modellfähigkeiten und unterstützt inzwischen lokale
Vision-Modelle. [Ollama: Modelldetails](https://docs.ollama.com/api-reference/show-model-details),
[Ollama: Vision](https://docs.ollama.com/capabilities/vision)

Ein Fähigkeitsname allein genügt nicht. Ein lokales Modell erhält die bereits
vorhandenen Szenenansichten erst, wenn es auf dem konkreten Rechner drei
Proben besteht:

1. Das Bild wird fachlich brauchbar verstanden.
2. Strukturierte Werkzeugaufrufe funktionieren weiterhin.
3. Die Bildfälle der Agenten-Suite sind mindestens so zuverlässig wie der
   reine Textweg.

Das Vorgabemodell `qwen3:14b` bleibt ohne Bild. Vision ist eine bewusste
Zusatzwahl, keine Voraussetzung für einfache Bedienung.

### 5.7 Kein Modellwechsel ohne Produktnachweis

Vor einer neuen Modellvorgabe wird die aktuelle Basislinie frisch gemessen.
Die 39 bestehenden Referenzanfragen bleiben erhalten und werden um die
Website-Hauptwege sowie echte Anfängerformulierungen ergänzt.

Gemessen werden:

- fachlich richtige Antwort oder Operation;
- Fragen statt Raten;
- ungültige Werkzeugaufrufe;
- Eingabe- und Ausgabe-Token;
- Zeit bis zur ersten Rückmeldung und Gesamtzeit;
- Zahl der Modell- und Werkzeugschritte;
- Einhaltung von Vorschau, Transaction und Nutzerfreigabe.

Ein neueres Modell wird nur dann Vorgabe, wenn der Gesamtwert für den Kunden
steigt. Ein Modellname oder eine größere Kontextzahl ist noch kein Fortschritt.

## 6. Projektbibliotheken: klare Auswahl

### 6.1 Sinnvoll als Entwicklungs- oder Bauwerkzeug

Diese Kandidaten verändern die ausgelieferte Anwendung nicht. Auch sie dürfen
erst nach Lizenzlisteneintrag, Festschreibung und grünem Nachweis aufgenommen
werden.

| Kandidat | Konkreter Nutzen | Lizenz | Einschätzung |
|---|---|---|---|
| [`pytest-qt`](https://github.com/pytest-dev/pytest-qt) | Vereinheitlicht Tests für Klicks, Tastatur, Signale, Zeitgrenzen und Ausnahmen in Qt-Slots | MIT | **sinnvoll** für ausgewählte asynchrone Hauptwege; kein mechanischer Umbau aller UI-Tests |
| [`Hypothesis`](https://hypothesis.readthedocs.io/en/latest/) | Erzeugt Randwerte und verkleinert Fehler auf ein einfaches Gegenbeispiel | MPL-2.0 | **sinnvoll** für Parameterausdrücke, Migrationen, Parser und schnelle Kernverträge; Geometrie-Korpus bleibt maßgeblich |
| [`pip-audit`](https://github.com/pypa/pip-audit) | Findet bekannte Schwachstellen in Umgebung und festgeschriebenem Satz | Apache-2.0 | **sinnvoll für CI**; nie automatisch reparieren, jeden Fund bewusst prüfen |
| [`cyclonedx-bom`](https://cyclonedx-bom-tool.readthedocs.io/en/latest/) | Erzeugt aus der tatsächlichen Bauumgebung eine Software-Stückliste | Apache-2.0 | **nur zusätzlich**, wenn der CycloneDX-Nachweis von `pip-audit` für Release, Lizenzen oder Abhängigkeitsgraph nicht ausreicht |

### 6.2 Nur bei einem gemessenen Einzelfall

| Kandidat | Nutzen | Entscheidungskriterium |
|---|---|---|
| [`py-spy`](https://github.com/benfred/py-spy) | Profiliert die laufende oder gebaute Anwendung ohne eingebauten Messcode | Als externes Entwicklerwerkzeug sinnvoll, wenn Windows- und PyInstaller-Pfad praktisch funktionieren; nicht in Anwendung oder Installer aufnehmen |
| [`superqt`](https://pyapp-kit.github.io/superqt/widgets/) | Bietet etwa beschriftete Bereichsregler, suchbare Auswahlen und aufklappbare Bereiche | Nur übernehmen, wenn ein Pilot mindestens zwei eigene komplexe Widgets sauber ersetzt und beide Solidon-Themen, High DPI und Zugänglichkeit trägt |

### 6.3 Warum keine neue allgemeine Laufzeitbibliothek empfohlen wird

Eine Bibliothek darf nicht aufgenommen werden, nur weil ihre Demonstration
modern aussieht. Sie muss mindestens eine dieser Fragen mit Ja beantworten:

- Entfernt sie nachweislich eine größere Menge eigenen Risikocodes?
- Schließt sie eine Funktion, die mit dem Bestand nicht zuverlässig möglich
  ist?
- Verbessert sie einen gemessenen Kundenweg deutlich?
- Trägt sie alle Plattformen, die Lizenzgrenze und das Paketformat?

Für eine neue Theme-, Agenten- oder Szenengraphbibliothek ist dieser Nachweis
derzeit nicht vorhanden.

## 7. Updates und Lieferqualität

Der vorhandene Weg bleibt richtig:

```text
neue Version entdecken
        ↓
gegen die grüne Referenz prüfen
        ↓
Geometrie, Oberfläche und Paketbau abnehmen
        ↓
Constraints neu festschreiben
        ↓
genau diesen Satz ausliefern
```

Ergänzend ist ein Liefernachweis sinnvoll:

- bekannte Schwachstellen des festgeschriebenen Satzes prüfen;
- eine CycloneDX-Stückliste aus der tatsächlichen Release-Umgebung erzeugen;
- Lizenzfreigabe, Constraints, Stückliste und gebautes Artefakt auf denselben
  Stand beziehen;
- Modell-, Prompt- und Regelsammlungsfassung ebenso nachvollziehbar halten wie
  Geometrieabhängigkeiten.

Der Cyber Resilience Act macht Sicherheits- und Schwachstellenprozesse für
Produkte mit digitalen Elementen zusätzlich relevant und sieht
Software-Stücklisten in der Herstellerdokumentation vor. Das ist hier eine
technische Vorbereitung, keine rechtliche Einzelfallbewertung. [EUR-Lex:
Cyber Resilience
Act](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=legissum%3A4797302)

## 8. Bewusste Nicht-Entscheidungen

- **Kein Qt-Quick/QML-Umbau:** hoher Migrationsaufwand ohne belegten
  Kundennutzen.
- **Kein `QtAsyncio` als Fundament:** das offizielle Modul ist als technische
  Vorschau ausgewiesen; die vorhandenen Worker und Abbruchverträge passen
  besser zu CPU-lastiger Geometrie. [QtAsyncio](https://doc.qt.io/qtforpython-6.8/PySide6/QtAsyncio/index.html)
- **Kein Fluent-Widget-Paket:** PyQt-Fluent-Widgets steht nichtkommerziell
  unter GPLv3 und verlangt für kommerzielle Nutzung eine andere Lizenz; GPL
  ist im Projekt ausgeschlossen. [Lizenzangabe des
  Projekts](https://github.com/zhiyiYo/PyQt-Fluent-Widgets)
- **Kein allgemeines Agentenframework:** LangChain oder LlamaIndex schaffen
  keine zusätzliche Geometriefähigkeit, vergrößern aber Abhängigkeiten und
  Angriffsfläche.
- **Kein SDK nur aus Bequemlichkeit:** Der kleine vorhandene HTTP-Adapter
  bleibt besser prüfbar, solange ein SDK keine konkret benötigte
  Protokollfunktion sicherer löst.
- **Keine Telemetrie:** Messungen bleiben lokal, in CI oder Teil ausdrücklich
  freigegebener Supportdaten.
- **Keine stillen Updates:** Die grüne, festgeschriebene Referenz bleibt immer
  der Rückweg.

## 9. Sinnvolle Entscheidungsfolge, ausdrücklich kein Zeitplan

Diese Reihenfolge ist keine Roadmap. Sie zeigt, welche Entscheidungen spätere
Experimente erst belastbar machen.

### Grundlage

1. Website-Versprechen als vollständige Kundenwege verstehen.
2. Einheitliche Interaktions- und Gestaltungssprache festhalten.
3. Reaktionszeit und Rückmeldung an den bestehenden Budgets messen.
4. Aktuellen Agentenprompt und aktuelle Modellgüte als Basislinie festhalten.

### Absicherung

1. Ausgewählte Qt-Hauptwege mit einer einheitlichen Testhilfe prüfen.
2. Randwerte in schnellen Kernverträgen systematisch erzeugen.
3. Schwachstellennachweis und Release-Stückliste an denselben Bau binden.

### Erst danach sinnvolle Experimente

1. Zweistufige Werkzeugentdeckung gegen den heutigen 23.891-Token-Auftrag.
2. Streaming mit vollständig gepufferten Werkzeugaufrufen.
3. Lokales Bildverständnis nach Fähigkeits- und Qualitätsprobe.
4. Einzelne Fremdwidgets nur bei nachgewiesenem Rückbau eigenen Codes.

## 10. Abnahmemaßstab

Eine spätere Umsetzung wäre nur dann eine Verbesserung, wenn alle Ebenen
belegt sind:

| Ebene | Nachweis |
|---|---|
| Kundenerlebnis | Die Website-Hauptwege funktionieren ohne CAD-Wissen und ohne Chat; Zustand und nächste Handlung sind verständlich. |
| Konsistenz | Dieselbe Absicht erzeugt über Oberfläche und Chat dieselbe registrierte Operation, Vorschau, Transaction und Undo-Grenze. |
| Leistung | Die Budgets aus Bauplan §31 werden in realen Hauptwegen eingehalten; längere Arbeit bleibt verständlich und abbrechbar. |
| KI | Keine Operation wird unerreichbar, keine unvalidierte Teilantwort läuft und Qualität sowie Gesamtzeit werden gegenüber einer frischen Basislinie nicht schlechter. |
| Oberfläche | Fokus, Tastatur, Skalierung, Zieh-Alternative, Zustandskodierung und eigene Widgets sind plattformübergreifend geprüft. |
| Auslieferung | Versionssatz, Lizenzfreigabe, grüner Bau, Schwachstellennachweis und Stückliste gehören zu genau demselben Artefakt. |

## 11. Schlussfolgerung

Die sinnvollste Verbesserungslinie besteht nicht aus möglichst vielen neuen
Funktionen oder Bibliotheken. Sie besteht aus drei klaren Schritten:

1. **Vorhandene Stärke verständlich verbinden:** Produktkompass,
   Operationsstack, Prüfbericht, Vorschau und Slicer-Übergabe bilden einen
   durchgehenden Kundenweg.
2. **KI kleiner und überprüfbarer machen:** weniger wiederholter Prompt,
   strukturierte Vorschläge, vollständige Solidon-Prüfung und kein
   Modellwechsel ohne Vergleich.
3. **Qualität beweisen:** wenige gezielte Entwicklungswerkzeuge, ein
   reproduzierbarer Versionssatz und ein Liefernachweis für genau das
   ausgelieferte Artefakt.

Damit bleibt Solidon einfach für Menschen ohne CAD-Kenntnisse, ohne seine
technische Tiefe zu verlieren. Es wirkt modern, weil es ruhig, schnell,
vorhersehbar und selbsterklärend ist — nicht weil es mehr sichtbare Technik
oder ein fremdes Designpaket besitzt.
