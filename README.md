# Solidon

Desktop-Anwendung zum **Konstruieren, Generieren und Bearbeiten** druckbarer
Modelle. Kern ist ein non-destruktiver Operationsstack über einer Szene mit
mehreren Objekten, benannten Projektparametern und Passungsbeziehungen. Ein
LLM-Agent steuert denselben Operations-API fern, den auch die Menüs benutzen.

**Geometrie rechnet Code, nie das Modell.** Ohne Netz, ohne Konto und ohne KI
bleibt alles außer dem Chat benutzbar.

Projektdateien tragen die Endung `.p3d`.

## Was Solidon nicht ist

Damit niemand das Falsche erwartet:

* **Kein CAD-Ersatz.** Es gibt Skizzen mit Zwangsbedingungen und einen exakten
  Kern für Verrundungen, Fasen und STEP — aber keine Historie aus
  parametrischen Features im Sinne von Fusion oder SolidWorks, und keine
  Baugruppenverwaltung. Der Hauptweg bleibt der Operationsstack auf Netzen;
  der exakte Kern ist der zweite Weg daneben, nicht der Ersatz für ein
  CAD-Programm.
* **Keine Passungen aus erzeugten Meshes.** Was ein Bildmodell erzeugt, ist eine
  Oberfläche, keine Konstruktion. Bohrungen und Passungen entstehen danach als
  eigene Operationen — nicht dadurch, dass man das erzeugte Netz vermisst.
* **Kein Slicer.** Die eingebaute Schichtanalyse sucht und bewertet; die
  Druckdatei kommt weiter aus dem Slicer. Beide Zahlenwelten bleiben getrennt
  ausgewiesen (§22.5).
* **Keine Cloud.** Kein Konto, keine Telemetrie, keine Projektablage im Netz.
  Ein Sprachmodell wird nur gefragt, wenn ein Schlüssel hinterlegt ist.

**Support** läuft über einen Kanal: **support@solidon3d.de**. Ein
Fehlerbericht entsteht im Programm unter *Hilfe → Fehlerbericht erstellen* und
bleibt so lange auf dem Rechner, bis jemand ihn selbst an diese Adresse
schickt. Für die Entwicklung bleiben daneben die Issues dieses Repositories.

---

## Die drei Wege

Beim Start liegen acht Beispielprojekte bereit — sie sind gleichzeitig
Dokumentation und Abnahmeprüfung (§37.2). Die ersten drei beantworten „wie
fange ich an", die übrigen „was kann das eigentlich":

| Projekt | Inhalt |
|---|---|
| `weg1-halterung-anpassen.p3d` | fremdes Modell einlesen, reparieren, bohren |
| `weg2-halter-konstruieren.p3d` | aus Parametern und Bausteinen neu konstruieren |
| `weg3-generiert-aufbereiten.p3d` | erzeugtes Mesh durch die Reparaturkette |
| `gehaeuse-mit-bausteinen.p3d` | Mutternfalle, Heat-Set-Buchse, Kabeldurchführung, Prüfstück |
| `schild-zweifarbig.p3d` | Schrift im Materialslot und Lettern als eigener Körper |
| `drucker-kalibrieren.p3d` | Toleranzleiter, Wandstärkenleiter, Überhangfächer |
| `aushoehlen-und-teilen.p3d` | teilen, verstiften, aushöhlen, anordnen |
| `dose-mit-deckel.p3d` | alles zusammen: benannte Maße, Bausteine, Deckel aus der Öffnung |

## Hilfe im Programm

**Hilfe → Handbuch** (F1) öffnet achtzehn Seiten: sieben geschriebene über
Verlauf, Parameter, Toleranzen und den Chat, elf erzeugte mit jeder Operation,
jedem Wert und jedem Bereich. Die zweite Hälfte kommt aus demselben Register
wie die Menüs — sie kann nicht veralten. Gesucht wird über den Text, nicht nur
über die Überschriften.

Auf der Kommandozeile gibt `solidon3d docs --manual` denselben Text aus.

---

## Unterlagen

| Datei | Inhalt |
|---|---|
| [3d-agent-bauplan.md](3d-agent-bauplan.md) | die Spezifikation — sagt **was** |
| [AGENTS.md](AGENTS.md) | Repository-Regeln — sagen **wie** |
| [ROADMAP.md](ROADMAP.md) | Arbeitsliste je Phase — sagt **was als Nächstes** |

## Entwickeln

```
python -m venv .venv
.venv/Scripts/python.exe -m pip install -c constraints.txt -e ".[dev,geom,ui]"
```

| Befehl | Zweck |
|---|---|
| `.venv/Scripts/python.exe -m pytest -q` | vollständige Suite |
| `.venv/Scripts/python.exe -m ruff check .` | Stil und Fehlerbilder |
| `.venv/Scripts/python.exe -m mypy` | Typprüfung (strict) |
| `.venv/Scripts/python.exe -m app.ui.app` | Anwendung starten |
| `.venv/Scripts/python.exe -m app.cli.main ops` | Operationen auflisten |
| `.venv/Scripts/python.exe -m app.i18n.extract` | Übersetzungskataloge abgleichen |
| `.venv/Scripts/python.exe tests/data/make_corpus.py` | Referenzkorpus erzeugen |
| `.venv/Scripts/python.exe tools/make_examples.py` | Beispielprojekte erzeugen |
| `.venv/Scripts/python.exe tools/run_agent_suite.py` | Agenten-Suite gegen ein echtes Modell |

Zum Starten per Doppelklick liegt unter `tools/start-solidon3d.cmd` eine
Verknüpfung.

## Paketieren

```
.venv/Scripts/python.exe -m pip install pyinstaller
.venv/Scripts/pyinstaller.exe packaging/solidon3d.spec --noconfirm
```

Ergebnis ist ein Ordner unter `dist/Solidon`. Die Bauläufe für Windows und
Linux stehen in `.github/workflows/build.yml`; sie laufen erst, wenn die Suite
auf allen drei Plattformen grün ist. Die Windows-Signierung braucht ein
Zertifikat als Repository-Secret — ohne das entsteht ein unsigniertes Paket
statt eines Fehlers.

OpenSCAD, Slicer, Ollama und ComfyUI werden **nicht** mitgeliefert, sondern
konfiguriert (§36, §38). Beim ersten Start zeigt die Anwendung, welche davon
gefunden wurden; Pflicht ist keines.

Unter **Hilfe → Zusätzliche Programme** steht dieselbe Liste mit einem Knopf
daneben. Python-Pakete (B-Rep-Kern, V-HACD, Schlüsselbund) holt Solidon über
`pip` in die eigene Umgebung, Programme über `winget`. Drei Regeln gelten dabei:
die Paketnamen stehen als Konstanten im Quelltext und kommen nie von außen,
installiert wird nur aus den offiziellen Quellen, und nichts läuft ungefragt —
gedrückt wird der Knopf von einem Menschen. Wo es von dort nicht geht (gebaute
Anwendung ohne `pip`, System ohne `winget`), steht die Begründung und die
offizielle Seite daneben.

Ohne funktionierendes OpenGL startet die Anwendung ohne 3D-Ansicht; erzwingen
lässt sich das mit `SOLIDON3D_NO_VIEWPORT=1`.

## Sprachmodell für den Chat

Der Chat braucht ein Modell; alles andere in Solidon kommt ohne aus. Der
Schlüssel wird über **Bearbeiten → Zugang zum Sprachmodell** im Schlüsselbund
des Systems abgelegt und reist nie mit der Projektdatei mit. Auf einem
Bauserver geht auch die Umgebungsvariable `SOLIDON3D_LLM_KEY`.

| Weg | Voraussetzung | Anmerkung |
|---|---|---|
| Eigener Schlüssel | Zugang beim Anbieter | Vorgabe, beste Werkzeugtreue |
| Lokal über Ollama | `ollama serve` auf Port 11434 | kein Schlüssel nötig |

Für den lokalen Weg braucht es ein Modell, das Werkzeugaufrufe zuverlässig
beherrscht — kleine Modelle scheitern daran reproduzierbar (§27). Alles unter
7B ist für die Op-Aufrufe erfahrungsgemäß zu wenig, aber **Größe allein sagt es
nicht**: manches große Modell gibt den Aufruf als Fließtext aus statt als
Aufruf, und dann sieht der Chat aus, als arbeite er, während nichts geschieht.

Entscheidend ist dabei, wie viele Werkzeuge im Spiel sind. Der Agent bietet
alle Operationen an — dreiundachtzig Schemata, rund 96 KB —, und daran fallen
kleinere Modelle, die mit einer Handvoll noch alles treffen. Vorgabe ist
darum `qwen3:14b`; `llama3.1:8b` ist schneller und kleiner, gibt unter der
vollen Last aber die Mehrzahl der Aufrufe als Text aus.

Ob ein Modell die Werkzeuge wirklich aufruft, misst

```
.venv/Scripts/python.exe tools/check_local_model.py qwen3:14b
```

Wie gut es dann mit den Referenzanfragen zurechtkommt, misst

```
.venv/Scripts/python.exe tools/run_agent_suite.py --backend ollama
```

## Modelle erzeugen (Weg 3)

**Datei → Modell erzeugen** spricht lokal mit einem laufenden ComfyUI auf Port
8188. Läuft keines, bleibt der Eintrag ausgegraut und sagt warum; alles andere
in Solidon funktioniert weiter.

Was zurückkommt, wird als Quelle ins Projekt eingebettet und danach im Stack
geladen und repariert — zwei Schritte, beide sichtbar, beide zurücknehmbar.
Prompt und Startwert stehen in der Quelle, damit die Datei sagt, woher die
Geometrie stammt.

Welche Knoten benutzt werden, steht in `app/core/backends/data/text_to_mesh.json`
und `image_to_mesh.json`. Die mitgelieferten Abläufe gehen von Hunyuan3D aus;
mit einem anderen Generator wird die Datei ersetzt, nicht der Quelltext.

## Was ohne zweites Programm geht

Der Grundsatz: was Solidon selbst kann, wird nicht ausgelagert. Externe
Programme bleiben für das, wo sie wirklich besser sind.

| Aufgabe | In Solidon | Sonst üblich |
|---|---|---|
| Text und Logo auf einer Fläche | **Beschriftung → Text aufbringen** | OpenSCAD, Blender |
| Logo oder Umriss als Körper | **Import → Zeichnung extrudieren** (SVG, DXF) | Inkscape + Blender |
| Fasen und Verrundungen | **Boolesch → Verrunden / Fase** (exakt, §30) | CAD-Programm |
| Erzeugtes Netz brauchbar machen | **Netz → Dezimieren, Glätten, Neu vernetzen** | MeshLab |
| Material sparen | **Druckvorbereitung → Aushöhlen** mit Entlüftung | Slicer-Infill oder Handarbeit |
| Linkes und rechtes Teil | **Transformation → Spiegeln** | zweite Konstruktion |
| Erste Schicht maßhaltig | **Elefantenfuß ausgleichen** aus dem Materialprofil | Slicer-Einstellung, projektfern |
| Toleranz messen statt raten | **Varianten erzeugen** (§28.3) | mehrere Exporte von Hand |
| Eine Passung prüfen, ohne das Teil zu drucken | **Druckvorbereitung → Prüfstück erzeugen** | von Hand nachmodellieren |
| Zweifarbige Beschriftung | **Text aufbringen** mit Materialslot, oder **Schriftzug als Körper** | zwei Konstruktionen |
| Deckel zu einer vorhandenen Schachtel | **Bausteine → Deckel erzeugen** | Hohlraum abmessen und neu zeichnen |
| Schraubdeckel für ein Glas oder eine Dose | **Bausteine → Drehdeckel erzeugen** | Gewindepaar von Hand konstruieren |
| Zehn Stück auf die Platte | **Objekt duplizieren** mit Anzahl | zehnmal kopieren, Stückzahl im Dateinamen |
| 3MF-Baugruppe aus dem Slicer öffnen | **Import** — die Teile kommen einzeln an | pro Teil eine STL exportieren |
| Etwas an eine angeklickte Fläche setzen | **Fläche wählen, Operation aufrufen** — Ort und Achse sind eingetragen | Koordinaten ablesen und eintippen |
| Eine Bohrung zwei Millimeter versetzen | **Doppelklick auf den Schritt im Verlauf** | zurücknehmen und neu bohren |
| Dichtung aus TPU im PETG-Gehäuse | **Druckvorbereitung → Material festlegen** | zwei Projekte |

Der Text kommt als Schriftumriss, nicht als Bild — die Kanten bleiben in jeder
Größe sauber, und DejaVu liegt bei, damit ein Projekt auf jedem Rechner gleich
aussieht. Beim Extrudieren einer Zeichnung werden innenliegende Konturen zu
Löchern.

Zweifarbig geht auf beiden Wegen, weil beide Drucker existieren: **Text
aufbringen** mit einem Materialslot legt die Schrift in eine eigene Gruppe, die
der 3MF-Export als Farbwechsel schreibt — eine Datei. **Schriftzug als Körper**
macht die Buchstaben zum eigenen Objekt, für den Drucker, an dem von Hand
gewechselt wird, und für Lettern zum Aufkleben.

Das **Prüfstück** schneidet einen Würfel um eine Stelle heraus, statt sie
nachzubauen: was gedruckt wird, ist die echte Geometrie mit der echten Toleranz.
Zwei Minuten statt zwei Stunden, und das Ergebnis gilt für das Teil.

Der **Deckel** wird aus der Öffnung geschnitten, nicht abgemessen: ein Schnitt
durch die Wand liefert Außenkontur und Hohlraum, der Kragen ist der Hohlraum
minus dem Spiel aus dem Materialprofil. Damit entscheidet dieselbe Zahl über den
Deckel wie über jede andere Passung — und wer sein Material kalibriert (§28.3),
verbessert damit auch Deckel, die vorher entstanden sind.

**Eine Szene darf mehrere Materialien haben.** Eine TPU-Dichtung in einem
PETG-Gehäuse schwindet anders, will mehr Spiel und quetscht die erste Schicht
weiter breit. Mit *Material festlegen* bekommt der einzelne Körper sein eigenes
Profil, und Toleranzen, Elefantenfuß und Passungsprüfung rechnen damit.

Draußen bleibt, was draußen besser ist: der **Slicer** schreibt die Druckdatei
(§22.5), das **Sprachmodell** und **ComfyUI** laufen, wo sie hingehören, und
**OpenSCAD** ist die Rückfallebene für Formen, für die es weder Baustein noch
Kern gibt.

## Exakte Körper (B-Rep) und STEP

Neben dem Netz-Kern steht ein zweiter mit echten Kanten (§30). Er kommt ins
Spiel, wenn eine STEP-Datei geladen wird oder ein exakter Quader bzw. Zylinder
angelegt wird — und er ist die Voraussetzung für **Verrunden** und **Fase
anbringen**: auf einem Netz wäre beides die Näherung einer Näherung.

Der Objektbaum kennzeichnet exakte Körper. **In ein Netz umwandeln** geht
jederzeit, der Rückweg nicht — ein Netz hat seine Kanten verloren. Der Schritt
steht aber im Verlauf, ein Undo holt den exakten Körper also zurück.

Exportiert wird ein solcher Körper als `STEP` mit Flächen und Kanten; STL und
3MF bleiben für alles, was auf den Drucker soll.

Der Kern ist optional:

```bash
.venv/Scripts/python.exe -m pip install -c constraints.txt -e ".[brep]"
```

Ohne ihn sagen die betroffenen Operationen das in einem Satz, und alles andere
in Solidon funktioniert unverändert.

## Mehr Teile als auf eine Platte passen

**Auf dem Bett anordnen** legt die Objekte nebeneinander und beginnt eine neue
Druckplatte, sobald die aktuelle voll ist — wie viele Platten erlaubt sind,
steht im Dialog. Was auch dann nicht passt, wird nicht weggelassen, sondern
gemeldet: eine Platte mehr würde helfen.

Jede Platte wird für sich geprüft — Bauraum und Kollisionen. Zwei Teile an
derselben Stelle auf verschiedenen Platten begegnen sich nie. Beim Export trägt
jede Datei ihre Platte im Namen (`projekt_platte2_teil_3von7.stl`), und der
Schieberegler unter der Ansicht schaltet zwischen den Platten um.

## Zu groß für das Bett (Auto Split)

**Bearbeiten → Automatisch teilen** schneidet ein Objekt, bis jedes Stück auf
die Platte passt. Die Trennebene wird gesucht, nicht geraten: über dieselbe
Schichtanalyse wie die Orientierungssuche, und bewertet wird eine Kontur statt
mehrerer dünner Brücken, ein prismatischer Verlauf und die Ausgewogenheit.

In jede Schnittfläche kommen zwei Passstifte — Durchmesser aus der Fläche, Spiel
aus dem kalibrierten Materialprofil — und zu jedem Stift entsteht ein
Passungspaar, das bei jeder Auswertung geprüft wird. Jeder Schnitt ist eine
eigene Operation: die Position bleibt eine Zahl, die man nachträglich ändern
kann, und ein Undo nimmt einen Schnitt zurück.

Der Schieberegler **Explosionsansicht** unter der Ansicht zieht die Teile zum
Ansehen auseinander. Er verschiebt nichts — Stack und Export bleiben, wie sie
sind.

## Farbe und Materialslots

Jedes Dreieck trägt einen Slot, jedes Objekt eine Liste von Materialslots (§20).
Zugewiesen wird über **Farbe → Slot zuweisen**, oder aus der Textur eines
erzeugten Modells über **Farbe → Farben in Slots umrechnen** — k-Means auf die
Anzahl eingelegter Filamente, mit gespeichertem Startwert, damit dieselbe Datei
dasselbe Ergebnis liefert. Das ist nie so fein wie die Bildschirmdarstellung.

**Bemalen** ist die dritte Möglichkeit: Leiste einschalten, Slot und Radius
wählen, ins Modell klicken. Der Pinsel läuft über die Oberfläche und hält an
Kanten an, statt um die Ecke zu malen — die Oberseite eines Deckels wird bemalt,
die Seitenwand nicht, ohne dass jemand eine Grenze zieht. Jeder Klick ist eine
Operation, also nimmt ein Undo einen Strich zurück.

Die Zuweisung überlebt Boolesche Operationen einschließlich der Voxelstufe. Beim
Export nach `3MF` wird daraus je Slot eine Materialgruppe; `STL` kennt keine
Farbe und verliert sie folgerichtig.

## Lizenz

Solidon ist proprietär — Copyright (c) 2026 RS Digital, alle Rechte
vorbehalten. Der vollständige Text steht in [LICENSE](LICENSE).

Zwei Teile stehen bewusst unter MIT, weil ihr Inhalt in den Ergebnissen der
Nutzer landet:

* die Bausteinbibliothek `app/core/knowledge/parts/`
* der Referenzkorpus `tests/data/`

Fremdbibliotheken behalten ihre eigenen Lizenzen; die Übersicht führt
[THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md). Geprüft wird das automatisch
gegen die Freigabeliste in `app/core/knowledge/data/licences.toml`.
