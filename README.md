# Solidon

Desktop-Anwendung zum **Konstruieren, Generieren und Bearbeiten** druckbarer
Modelle. Kern ist ein non-destruktiver Operationsstack über einer Szene mit
mehreren Objekten, benannten Projektparametern und Passungsbeziehungen. Ein
LLM-Agent steuert denselben Operations-API fern, den auch die Menüs benutzen.

**Geometrie rechnet Code, nie das Modell.** Nach der einmaligen
Gerätefreischaltung bleibt Solidon ohne Netz und ohne Konto vollständig
nutzbar; ein Arbeitsrechner ohne Netz wird per Anfrage- und Antwortdatei über
ein zweites Gerät aktiviert. Ohne KI bleibt nur der Chat aus.

Projektdateien tragen die Endung `.p3d`.

## Version 0.3.0 — die öffentliche Demo

Die aktuelle Version ist eine **Demo**: vollständig, unentgeltlich, ohne
Schlüssel und ohne Konto, **befristet bis zum 30. Oktober 2026**. Danach
startet sie nicht mehr — kein Betrachtermodus, keine halbe Version, die
niemand pflegt. Projektdateien sind davon unberührt: eine `.p3d` ist ein
ZIP-Archiv mit JSON darin und bleibt lesbar.

Der Stichtag steht in `app/core/activation/store.py` (`DEMO_UNTIL`) und
nirgends sonst. Am **31. Oktober 2026** bleibt die Demo gestoppt; am
**1. November 2026** startet die Verkaufsversion 1.0. Sie trägt bei
`DEMO_UNTIL` und `TRIAL_FROM` jeweils `None`: kein Demo-Stichtag und zunächst
keine Testphase. Ab dem 1. November ausgestellte Verkaufsschlüssel öffnen
schreibende Funktionen erst mit dem passenden Geräte-Zertifikat; bereits
ausgegebene Bestandsschlüssel bleiben ohne nachträgliche Aktivierung gültig.
Der gepflegte 14-Tage-Pfad bleibt im Code,
aber nur ein späterer neuer Bau mit gesetztem `TRIAL_FROM` kann ihn anbieten.
Das Konzept dahinter steht in `konzepte/konzept-demo-2026-10.md`.

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

**Support** läuft über einen Kanal: **support@solidon3d.de**. Unter *Hilfe →
Rückmeldung senden* geht ein Vorschlag, ein Fehler oder eine Frage direkt aus
dem Programm dorthin — mit Bildschirmfoto, Protokoll und auf Wunsch der
laufenden Sitzung, deren Container den Fehler exakt reproduziert (§16.2). Was
mitgeht, steht vorher in der Vorschau; gesendet wird nur auf Knopfdruck, und
wer nichts aus der Hand geben will, legt im selben Dialog nur einen Ordner auf
dem eigenen Rechner ab. Telemetrie gibt es weiterhin keine. Für die
Entwicklung bleiben daneben die Issues dieses Repositories.

---

## Die vier Wege

Beim Start liegen elf Beispielprojekte bereit — sie sind gleichzeitig
Dokumentation und Abnahmeprüfung (§37.2). Die ersten vier beantworten „wie
fange ich an", die übrigen „was kann das eigentlich". Auf dem Startbildschirm
stehen dafür die Handlungen statt der internen Wegnummern: vorhandenes Modell
anpassen, eigenes Teil bauen, ein erzeugtes Modell vorbereiten oder eine Figur
frei formen.

| Projekt | Inhalt |
|---|---|
| `weg1-halterung-anpassen.p3d` | vorhandenes Modell öffnen, prüfen und eine Bohrung ergänzen |
| `weg2-halter-konstruieren.p3d` | eigenes Teil aus Grundformen und fertigen Bausteinen bauen |
| `weg3-generiert-aufbereiten.p3d` | ein Modell aus Text oder Bild druckbar vorbereiten |
| `weg4-figur-formen.p3d` | einfache Körper verbinden und wie Ton frei formen |
| `gehaeuse-mit-bausteinen.p3d` | Mutternfalle, Heat-Set-Buchse, Kabeldurchführung, Prüfstück |
| `schild-zweifarbig.p3d` | Schrift mit eigenem Filament und Lettern als eigener Körper |
| `skizze-mit-massen.p3d` | Umriss aus Bedingungen: der Durchmesser folgt dem Parameter |
| `drucker-kalibrieren.p3d` | Toleranzleiter, Wandstärkenleiter, Überhangfächer |
| `aushoehlen-und-teilen.p3d` | teilen, verstiften, aushöhlen, anordnen |
| `dose-mit-deckel.p3d` | alles zusammen: benannte Maße, Bausteine, Deckel aus der Öffnung |
| `passung-nach-materialwechsel.p3d` | der Deckel soll aus TPU kommen — und passt nicht mehr |

## Hilfe im Programm

**Hilfe → Handbuch** (F1) öffnet zwei Sorten Seiten. Geschriebene über die
ersten fünfzehn Minuten, das Fenster, das Zeichnen, Verlauf, Parameter,
Toleranzen, Bausteine, den Chat und ein Wörterbuch — dazu je eine erzeugte
Seite pro Kategorie des Registers, mit jeder Operation, jedem Wert und jedem
Bereich. Die zweite Hälfte kommt aus demselben Register wie die Menüs — sie
kann nicht veralten, und eine neue Operation kann nicht dazukommen, ohne dort
aufzutauchen. Gesucht wird über den Text, nicht nur über die Überschriften.
Abbildungen gehören dazu; keine davon wird von Hand gepflegt.

**Hilfe → Solidon3D unterstützen** öffnet zunächst nur einen lokalen Dialog.
Er erklärt die freiwillige Zahlung und ihre Bedingungen; erst der Knopf darin
öffnet die Zahlungsseite von PayPal im Standardbrowser. Die Solidon3D-Webseite
liegt nicht dazwischen.

Auf der Kommandozeile gibt `solidon3d docs --manual` denselben Text aus.

---

## Unterlagen

| Datei | Inhalt |
|---|---|
| [3d-agent-bauplan.md](3d-agent-bauplan.md) | die Spezifikation — sagt **was** |
| [AGENTS.md](AGENTS.md) | Repository-Regeln — sagen **wie** |
| [ROADMAP.md](ROADMAP.md) | Arbeitsliste je Phase — sagt **was als Nächstes** |
| [ROADMAP-ARCHIV.md](ROADMAP-ARCHIV.md) | die abgeschlossenen Abschnitte, datiert — sagt **was schon versucht wurde** |
| [konzepte/](konzepte/README.md) | Konzepte und Durchsichten — sagen **warum**, mit den Messwerten daneben |

## Entwickeln

Entwicklung und CI verwenden CPython 3.14.7. Die 3D-Ansicht bindet VTK direkt
ein; pygfx bleibt als zweiter Renderer für den Vergleich vorhanden.

```
python -m venv .venv
.venv/Scripts/python.exe -m pip install -c constraints.txt -e ".[dev,geom,ui,brep]"
git config core.hooksPath .githooks
```

Die dritte Zeile ist einmal je Arbeitsplatz nötig und schaltet die Git-Hooks des
Projekts ein — derzeit einen: Er pusht jeden Commit sofort. Ohne die Zeile
passiert nichts weiter, als dass Commits liegen bleiben, bis jemand von Hand
pusht. `core.hooksPath` ist eine lokale Einstellung; Git holt sie sich nicht aus
dem Repository, deshalb steht sie hier und nicht in einer Datei.

| Befehl | Zweck |
|---|---|
| `bash .claude/.state/oberflaechen-durchsicht-2026-08-19/suite-getrennt.sh` | Suite wie in der CI, Fensterdateien getrennt |
| `.venv/Scripts/python.exe -m pytest -q -m performance` | Leistungsbudgets aus §31 |
| `.venv/Scripts/python.exe -m ruff check .` | Stil und Fehlerbilder |
| `.venv/Scripts/python.exe -m ruff format --check .` | Formatierung prüfen |
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
.venv/Scripts/python.exe -m pip install -c constraints.txt pyinstaller
.venv/Scripts/pyinstaller.exe packaging/solidon3d.spec --noconfirm
```

Ergebnis ist ein Ordner unter `dist/Solidon3D`. Die Bauläufe für Windows,
Linux und beide Mac-Architekturen stehen in `.github/workflows/build.yml`; sie
laufen erst, wenn die Suite auf den vorgesehenen Plattformen grün ist. Das
Windows-Paket wird dort gebaut, aber lokal signiert: `tools/sign_release.py`
holt die prüfsummengebundene Übergabe des Laufs, signiert Anwendung und
Setup-Datei mit dem Certum-Zertifikat und legt das Ergebnis unter `dist/`.
Der Baulauf selbst liefert ein unsigniertes Paket mit sichtbarer Warnung.

Aus demselben Ordner entstehen unter Linux drei Formate. Das **tar.gz** ist der
Bau selbst; das **AppImage** ist eine Datei, die ohne Installation läuft, und
das **Flatpak** der Weg in die Software-Verwaltung mit Aktualisierung und
Sandbox. Gebaut werden sie von `tools/make_linux_packages.py`, das die Werte aus
`app/branding.py` liest und daraus Menüeintrag, Flatpak-Manifest und
AppStream-Beschreibung schreibt. Ausgeliefert werden ab der nächsten Version
AppImage und Flatpak; das Archiv bleibt ein Bauartefakt.

```
python tools/make_linux_packages.py --files    # nur die Beschreibungen
python tools/make_linux_packages.py            # beide Pakete, braucht Linux
```

`appimagetool` und `flatpak-builder` sind externe Programme und werden nicht
mitgeliefert (§36). Das Flatpak hat dieselbe Netzfähigkeit wie Windows und
macOS: Aktualisierungsprüfung, Rückmeldung und ausdrücklich konfigurierte
Onlinedienste funktionieren. Daraus entstehen weder Konto noch Telemetrie;
ohne Netz bleibt alles außer Chat und bewusst gewählten Onlinediensten
benutzbar.

Slicer, Ollama und ComfyUI werden **nicht** mitgeliefert, sondern konfiguriert
(§36, §38). Beim ersten Start zeigt die Anwendung, welche davon gefunden
wurden; Pflicht ist keines.

Unter **Hilfe → Zusätzliche Programme** steht dieselbe Liste mit einem Knopf
daneben. Python-Pakete (B-Rep-Kern, V-HACD, Schlüsselbund) holt Solidon über
`pip` in die eigene Umgebung, Programme über `winget`. Drei Regeln gelten dabei:
die Paketnamen stehen als Konstanten im Quelltext und kommen nie von außen,
installiert wird nur aus den offiziellen Quellen, und nichts läuft ungefragt —
gedrückt wird der Knopf von einem Menschen. Wo es von dort nicht geht (gebaute
Anwendung ohne `pip`, System ohne `winget`), steht die Begründung und die
offizielle Seite daneben.

Lokale Dienste lassen sich dort auch starten. Für ComfyUI erkennt Solidon die
offizielle **Comfy Desktop**-App und die `comfy`-Kommandozeile; *Ort angeben …*
trennt deshalb zwischen einer lokalen App und der Web-/Netzadresse eines schon
laufenden Dienstes. Beide Angaben bleiben getrennt erhalten. *Lokal starten*
wechselt bewusst auf Port 8188; die zuvor eingetragene Netzadresse bleibt für
einen späteren Wechsel gespeichert.

Die vorgegebene VTK-Ansicht braucht OpenGL 3.2 oder neuer, unter Linux X11
beziehungsweise Xwayland. `SOLIDON3D_NO_VIEWPORT=1` startet ohne 3D-Ansicht.
Für den internen Renderer-Vergleich wählt `SOLIDON_RENDERER=gfx` pygfx über
Vulkan, Metal oder Direct3D 12; es gibt keinen automatischen Wechsel zwischen
den Renderern.

## Sprachmodell für den Chat

Der Chat braucht ein Modell; alles andere in Solidon kommt ohne aus. Der
Schlüssel wird über **Bearbeiten → Chat einrichten** im Schlüsselbund
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
alle 95 registrierten Operationen und elf Analyse- und Dialogwerkzeuge an —
106 Schemata, für Ollama kompakt rund 105 KB. Daran fallen kleinere Modelle,
die mit einer Handvoll noch alles treffen. Vorgabe ist darum `qwen3:14b`;
`llama3.1:8b` ist schneller und kleiner, gibt unter der vollen Last aber die
Mehrzahl der Aufrufe als Text aus.

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
in Solidon funktioniert weiter. Ein gefundenes lokales ComfyUI lässt sich unter
**Hilfe → Zusätzliche Programme** mit *Lokal starten* öffnen. Die Zeile weist
zusätzlich aus, ob gerade das lokale Backend oder eine Web-/Netzadresse aktiv
ist.

Was zurückkommt, wird als Quelle ins Projekt eingebettet und danach im Stack
geladen und repariert — zwei Schritte, beide sichtbar, beide zurücknehmbar.
Prompt und Startwert stehen in der Quelle, damit die Datei sagt, woher die
Geometrie stammt.

### Einrichten

ComfyUI allein erzeugt noch nichts — es braucht die Knoten und das Modell dazu.
Beides legt **Solidon selbst** hin: *Hilfe → Zusätzliche Programme*, in der
Zeile von ComfyUI der Knopf *Knoten und Modell einrichten …*.

Der Dialog findet ComfyUI an den üblichen Stellen und liest bei **Comfy
Desktop** dessen eigene Installationsaufstellung. Sonst lässt sich der Ordner
angeben, in dem `custom_nodes` und `main.py` liegen. Solidon legt die Knoten
hinein, holt den TripoSG-Quelltext, richtet zwei Stellen darin, zieht die
fehlenden Pakete nach und lädt die Gewichte — rund 7,5 GB, abwählbar. Abbrechen
geht zwischen den Schritten; was schon da ist, bleibt. Danach ComfyUI **einmal
neu starten**: Es liest seine Knoten beim Start.

Für den Weg über **Text** kommt ein SDXL-Modell unter `models/checkpoints`
dazu; für den Weg über ein **Bild** wird keines gebraucht.

Dasselbe von der Kommandozeile, für den Entwicklungsbaum:

```
python tools/setup_comfyui.py
```

Die Arbeit steckt in `app/core/backends/comfy_setup.py`, die Knoten in
`app/core/backends/data/comfyui/` — beides reist im Paket mit. Vorher lag es
unter `tools/`, und die Anwendung nannte einen Befehl, den ein Kunde nicht
ausführen kann.

Fehlt die Knotensammlung, sagt Solidon das beim Erzeugen und führt zu diesem
Dialog — es schickt niemanden Gewichte suchen, dem die Knoten fehlen.

### Welches Modell, und warum dieses

Der mitgelieferte Ablauf benutzt **TripoSG**, das unter der MIT-Lizenz steht —
Quelltext wie Gewichte. Das ist der Grund für die Wahl: Das verbreitetere
Hunyuan3D nimmt in seiner Lizenz die Europäische Union ausdrücklich aus.

Gemessen auf einer RTX 4080 braucht ein Körper rund 13 Sekunden und kommt mit
300 000 bis 600 000 Dreiecken geschlossen und aus einem Stück heraus. Die
Vorgaben im Ablauf sind nicht geraten: `octree_depth` steht auf 8, weil 9 bei
vierfacher Dreieckszahl keinen sichtbaren Unterschied brachte, und `steps` auf
50, weil dünne Flächen bei 25 sichtbar ausfransen.

Welche Knoten benutzt werden, steht in `app/core/backends/data/text_to_mesh.json`
und `image_to_mesh.json`. Die Dateien nennen Rollen und keine Dateinamen: mit
einem anderen Generator wird die Datei ersetzt, nicht der Quelltext.

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
| Zweifarbige Beschriftung | **Text aufbringen** mit eigenem Filament, oder **Schriftzug als Körper** | zwei Konstruktionen |
| Deckel zu einer vorhandenen Schachtel | **Bausteine → Deckel erzeugen** | Hohlraum abmessen und neu zeichnen |
| Schraubdeckel für ein Glas oder eine Dose | **Bausteine → Drehdeckel erzeugen** | Gewindepaar von Hand konstruieren |
| Zehn Stück auf die Platte | **Objekt duplizieren** mit Anzahl | zehnmal kopieren, Stückzahl im Dateinamen |
| 3MF-Baugruppe aus dem Slicer öffnen | **Import** — die Teile kommen einzeln an | pro Teil eine STL exportieren |
| Etwas an eine angeklickte Fläche setzen | **Fläche wählen, Operation aufrufen** — Ort und Achse sind eingetragen | Koordinaten ablesen und eintippen |
| Eine vorhandene Bohrung in STL oder STEP ändern | **Bohrung anklicken → Bohrung ändern** — nur den neuen Durchmesser eintragen | Stopfen bauen, neu bohren oder CAD-Historie rekonstruieren |
| Eine Bohrung zwei Millimeter versetzen | **Doppelklick auf den Schritt im Verlauf** | zurücknehmen und neu bohren |
| Dichtung aus TPU im PETG-Gehäuse | **Druckvorbereitung → Material festlegen** | zwei Projekte |

Der Text kommt als Schriftumriss, nicht als Bild — die Kanten bleiben in jeder
Größe sauber, und DejaVu liegt bei, damit ein Projekt auf jedem Rechner gleich
aussieht. Beim Extrudieren einer Zeichnung werden innenliegende Konturen zu
Löchern.

Zweifarbig geht auf beiden Wegen, weil beide Drucker existieren: **Text
aufbringen** mit einem eigenen Filament legt die Schrift in eine eigene Gruppe,
die der 3MF-Export als Farbwechsel schreibt — eine Datei. **Schriftzug als Körper**
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
(§22.5), das **Sprachmodell** und **ComfyUI** laufen, wo sie hingehören.

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

## Farbe und Filamente

Intern trägt jedes Dreieck einen Materialslot; in der Bedienung wählt man ein
**Filament mit Name und Farbe**, keine Nummer (§20). Der projektübergreifende
Filamentkatalog darf beliebig viele Spulen führen. Je Objekt bleiben höchstens
acht gleichzeitig benutzte Filamente möglich, entsprechend dem 3MF- und
Druckerweg.

Zugewiesen wird über **Farbe → Teil färben** für den ganzen Körper oder
**Farbe → Fläche färben** für die erkannte Fläche unter dem Zeiger. Die
Flächengrenze kommt aus der Merkmalserkennung und wandert bei späteren
Maßänderungen mit; es gibt keinen punktfesten Pinsel und keinen Radius mehr.
Aus der Textur eines erzeugten Modells kann **Textur in Filamente umrechnen**
die Zahl eingelegter Filamente ableiten — mit gespeichertem Startwert, damit
dieselbe Datei dasselbe Ergebnis liefert.

Name, Farbe und die je Spule übersteuerten Druckwerte bleiben beim direkten
3MF-Export und bei der Slicer-Übergabe zusammen. Die Zuweisung überlebt
Boolesche Operationen einschließlich der Voxelstufe. `STL` kennt keine Farbe
und verliert sie folgerichtig.

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
