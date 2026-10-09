# Solidon

Desktop-Anwendung zum **Konstruieren, Generieren und Bearbeiten** druckbarer
Modelle. Kern ist ein non-destruktiver Operationsstack über einer Szene mit
mehreren Objekten, benannten Projektparametern und Passungsbeziehungen. Ein
LLM-Agent steuert denselben Operations-API fern, den auch die Menüs benutzen.

**Geometrie rechnet Code, nie das Modell.** Nach der einmaligen
Gerätefreischaltung bleibt Solidon ohne Netz und ohne Konto vollständig
nutzbar; ein Arbeitsrechner ohne Netz wird per Anfrage- und Antwortdatei über
ein zweites Gerät aktiviert. Konstruktion, Bearbeitung und Druckvorbereitung
funktionieren ohne KI. Für den Chat und die Erzeugung aus Text oder Bild
werden die jeweils eingerichteten Modelle benötigt.

Projektdateien tragen die Endung `.p3d`.

## Die öffentliche Demo

Die aktuelle Version ist eine **Demo**: vollständig, unentgeltlich, ohne
Schlüssel und ohne Konto, **befristet bis zum 30. November 2026**. Danach
startet sie nicht mehr — kein Betrachtermodus, keine halbe Version, die
niemand pflegt. Projektdateien sind davon unberührt: eine `.p3d` ist ein
ZIP-Archiv mit JSON darin und bleibt lesbar.

Der Stichtag steht in `app/core/activation/store.py` (`DEMO_UNTIL`) und
nirgends sonst. Ab dem **1. Dezember 2026** bleibt die Demo gestoppt, und am
selben Tag startet die Verkaufsversion 1.0. Sie trägt bei
`DEMO_UNTIL` und `TRIAL_FROM` jeweils `None`: kein Demo-Stichtag und zunächst
keine Testphase. Ab dem 1. November ausgestellte Verkaufsschlüssel öffnen
schreibende Funktionen erst mit dem passenden Geräte-Zertifikat; bereits
ausgegebene Bestandsschlüssel bleiben ohne nachträgliche Aktivierung gültig.
Der gepflegte 14-Tage-Pfad bleibt im Code,
aber nur ein späterer neuer Bau mit gesetztem `TRIAL_FROM` kann ihn anbieten.
Das Konzept dahinter steht in `konzepte/konzept-demo-2026-10.md`.

Verkauft wird 1.0 ab dem **1. Dezember 2026, 10:00 Uhr**, in zwei Lizenzarten
mit demselben Funktionsumfang, beide als Einmalkauf mit allen Updates von 1.x:
**privat 69 €** und **gewerblich 199 €**, jeweils als Einstiegspreis bis zum
31. Januar 2027; ab dem 1. Februar 2027 kostet die private Lizenz 99 € und die
gewerbliche 249 €. Was die beiden unterscheidet (Personen, Rechner, Support,
Weitergabe im Betrieb), regeln `AGB.md` §2 und `EULA.md`; die Startseite zeigt
es in ihrem Abschnitt „Preis und Lizenz".

## Herunterladen

Die Pakete stehen auf der [Downloadseite](https://solidon3d.de/#download):
für Windows eine Setup-Datei, für Linux ein AppImage und ein Flatpak, für den
Mac je ein Paket für Apple Silicon und für Intel. Welche Version gerade
veröffentlicht ist, steht dort; was jede Version gebracht hat, in
[changelog/de.md](changelog/de.md). Dieses Repository trägt dazu den
Entwicklungsstand danach.

Solidon läuft unter Windows 10 ab Version 1809 und Windows 11 auf x64, unter
macOS ab Version 13 und unter Linux auf x64 mit X11 oder Xwayland. Die
3D-Ansicht braucht eine Grafik mit Direct3D 12, Vulkan oder Metal. Findet
Solidon keine passende, startet es ohne 3D-Ansicht; `SOLIDON3D_NO_VIEWPORT=1`
lässt sie ausdrücklich weg. Arbeitsspeicher, Speicherplatz und
Bildschirmgröße nennt die Website unter
[Systemvoraussetzungen](https://solidon3d.de/#voraussetzungen).

Das Flatpak fragt wie die anderen Pakete nach Updates, sendet Rückmeldungen
und erreicht eingerichtete Onlinedienste.

## Was Solidon nicht ist

Damit niemand das Falsche erwartet:

* **Kein vollständiger Ersatz für ein CAD-System.** Skizzen mit Bedingungen,
  benannte Maße und ein exakter Kern ermöglichen eigene Konstruktionen.
  Eine eingelesene STL erhält dadurch keine ursprüngliche CAD-Historie;
  es gibt auch keine Baugruppenverwaltung mit Gelenken und Bewegungen.
  Verrundungen und Fasen funktionieren sowohl an geeigneten erkannten
  Netzkanten als auch an exakten Körpern.
* **Keine Passungen aus erzeugten Meshes.** Was ein Bildmodell erzeugt, ist eine
  Oberfläche, keine Konstruktion. Bohrungen und Passungen entstehen danach als
  eigene Operationen — nicht dadurch, dass man das erzeugte Netz vermisst.
* **Kein Slicer.** Die eingebaute Schichtanalyse sucht und bewertet; die
  Druckdatei kommt weiter aus dem Slicer. Beide Zahlenwelten bleiben getrennt
  ausgewiesen (§22.5).
* **Keine Cloud-Ablage von Projekten.** Kein Konto, keine Telemetrie, keine
  Projektablage im Netz. Der Chat verwendet den ausdrücklich eingerichteten
  Onlinedienst oder ein lokales Modell über Ollama.

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

Beim Start liegen zwölf Beispielprojekte bereit — sie sind gleichzeitig
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
| `drucker-kalibrieren.p3d` | Toleranz-Testkörper, Wandstärkenleiter, Überhangfächer |
| `aushoehlen-und-teilen.p3d` | teilen, verstiften, aushöhlen, anordnen |
| `zu-gross-automatisch-teilen.p3d` | zu lang fürs Bett: automatisch in drei Stücke mit Passstiften geteilt |
| `dose-mit-deckel.p3d` | alles zusammen: benannte Maße, Bausteine, Deckel aus der Öffnung |
| `passung-nach-materialwechsel.p3d` | der Deckel soll aus TPU kommen — und passt nicht mehr |

## Hilfe im Programm

**Hilfe → Handbuch** (F1) beginnt bei „Wo fange ich an?“. Bildanleitungen
zeigen jeden Schritt an einem Bild der echten Oberfläche, mit Nummer und Rahmen
auf dem Knopf, um den es geht. Danach folgen Erklärseiten zu den Bereichen des
Programms, Hilfe bei Problemen und zum Nachschlagen ein Wörterbuch und je eine
erzeugte Seite pro Kategorie des Registers, mit jeder Operation, jedem Wert und
jedem Bereich. Die erzeugte Hälfte kommt aus demselben Register wie die
Bedienelemente; neue Operationen stehen dadurch von selbst darin. F1 im Dialog
einer Operation schlägt ihre Anleitung auf oder ihren Eintrag im
Nachschlageteil. Die Suche ordnet nach Treffern und versteht auch eigene Wörter
wie „abrunden“. Bilder und Website-Fassung entstehen bei jedem Release neu;
keine Abbildung wird von Hand gepflegt.

**Hilfe → Solidon3D unterstützen** öffnet zunächst nur einen lokalen Dialog.
Er erklärt die freiwillige Zahlung und ihre Bedingungen; erst der Knopf darin
öffnet die Zahlungsseite von PayPal im Standardbrowser. Die Solidon3D-Webseite
liegt nicht dazwischen.

Auf der Kommandozeile gibt `solidon3d docs --manual` denselben Text aus.

## Zusätzliche Programme

Slicer, Ollama und ComfyUI liegen nicht bei, sie werden eingerichtet (§36,
§38). Pflicht ist keines; beim ersten Start zeigt Solidon, welche es gefunden
hat.

Als Slicer kennt Solidon PrusaSlicer, SuperSlicer, OrcaSlicer, ElegooSlicer,
Bambu Studio, Creality Print, Anycubic Slicer Next und Cura. Unter Linux
findet es OrcaSlicer, Bambu Studio und PrusaSlicer auch als Flatpak.

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

## Sprachmodell für den Chat

Der Chat braucht ein Sprachmodell. Manuelle Konstruktion, Bearbeitung und
Druckvorbereitung kommen ohne aus. Der Schlüssel wird über
**Bearbeiten → Chat einrichten** im Schlüsselbund
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
alle registrierten Operationen sowie Analyse- und Dialogwerkzeuge an; einem
lokalen Modell stehen je Anfrage nur die gemeinten mit allen Feldern da, die
übrigen in Kurzform, die es bei Bedarf nachfordert. Der Auftrag belegt damit
ein Viertel bis ein Drittel des Kontextfensters statt fast des ganzen.

Empfohlen sind die Modelle, die in der Werkzeugprobe mindestens sieben von
acht Aufrufen treffen und bei einer unklaren Anfrage nachfragen, statt zu
raten (`OLLAMA_SUGGESTIONS` in `app/core/backends/llm.py`):

| Modell | Grafikspeicher | Suite | Anmerkung |
|---|---|---|---|
| `qwen3.5:9b` | 7,4 GB | 21/39 | ganz auf der Karte ab 10 GB, mit 8 GB zwei- bis dreimal langsamer; fragt seltener nach |
| `gpt-oss:20b` | 12,9 GB | 10/39 | Karte mit 16 GB; für einzelne Anweisungen |
| `qwen3:14b` | 13,6 GB | 22/39 | Vorgabe; denkt vor jeder Antwort, Karte mit 16 GB |
| `qwen3:30b-a3b` | mehr als 16 GB | — | auf 16 GB rechnet ein Drittel der Prozessor |

Die Spalte „Suite“ zählt, wie viele der 39 Referenzanfragen das Modell löst,
gemessen auf einer RTX 4080.

Gemessen und nicht empfohlen (`OLLAMA_UNSUITABLE`): `qwen3.5:9b-q8_0` (die
kleinere Fassung trifft öfter), `gemma4:12b`, `granite4.1:8b`, `llama3.1:8b`,
`mistral-nemo`, `qwen2.5-coder:14b`, `llama3`. Passt ein Modell nicht ganz in
den Grafikspeicher, rechnet der Prozessor mit, und jede Antwort dauert ein
Vielfaches.

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

ComfyUI bringt die Knoten für Weg 3 ab Version 0.35 selbst mit; es fehlen nur
die Modelle. Die lädt **Solidon selbst**: *Hilfe → Zusätzliche Programme*, in
der Zeile von ComfyUI der Knopf *Modelle einrichten …*.

Der Dialog findet ComfyUI an den üblichen Stellen und liest bei **Comfy
Desktop** dessen eigene Installationsaufstellung. Sonst lässt sich der Ordner
angeben, in dem `custom_nodes` und `main.py` liegen. Zuerst prüft er die
Version von ComfyUI; ist sie zu alt, sagt er es, bevor etwas geladen wird. Dann
lädt er das Modell für den Weg aus Bild (rund 8 GB) und auf Wunsch das
Bildmodell für den Weg aus Text (rund 8,3 GB), jede Datei in einem festen
Stand und mit Prüfsumme. Abbrechen geht auch mitten im Download; ein neuer
Lauf setzt fort.

Fehlt beim Erzeugen ein Modell, führt Solidon zu diesem Dialog. Fehlt ein
Knoten, ist ComfyUI zu alt, und Solidon sagt, ab welcher Version es geht.

### Welche Modelle, und unter welcher Lizenz

| Aufgabe | Modell | Lizenz |
|---|---|---|
| Körper aus einem Bild | TRELLIS.2-4B von Microsoft | MIT |
| Bild lesen (in TRELLIS.2) | DINOv3 ViT-L/16 von Meta | DINOv3 License: weltweit und gewerblich, mit Nutzungsbedingungen (u. a. keine Waffen, Handelskontrollen) |
| Freistellen | BiRefNet | MIT |
| Bild aus Text | FLUX.2 [klein] 4B von Black Forest Labs, Textkodierer Qwen3-4B | Apache-2.0 |

Solidon liefert keines davon mit; die Einrichtung lädt sie in das ComfyUI des
Nutzers.

Bis Oktober 2026 lief Weg 3 über **TripoSG**. Dessen Wurzellizenz ist MIT, ein
Teil des Quelltexts steht aber unter der Tencent Hunyuan Community License und
der FlashVDM-Lizenz, die die Europäische Union, Großbritannien und Südkorea
ausnehmen. Die Einrichtung räumt, was sie damals selbst in ComfyUI angelegt hat.

## Was ohne zweites Programm geht

Der Grundsatz: was Solidon selbst kann, wird nicht ausgelagert. Externe
Programme bleiben für das, wo sie wirklich besser sind.

| Aufgabe | In Solidon | Sonst üblich |
|---|---|---|
| Text auf einer Fläche | **Fläche wählen → rechts Text aufbringen** | OpenSCAD, Blender |
| Logo oder Umriss als Körper | **Datei → Modell einfügen** (SVG, DXF) | Inkscape + Blender |
| Fasen und Verrundungen | **Kante wählen → rechts Verrunden / Fase anbringen** — am Netz oder exakten Körper | CAD-Programm |
| Erzeugtes Netz brauchbar machen | **Teil wählen → rechts Dreiecke verringern, Glätten, Dreiecke angleichen** | MeshLab |
| Material sparen | **Teil wählen → rechts Aushöhlen** mit Entlüftung | Slicer-Infill oder Handarbeit |
| Linkes und rechtes Teil | **Teil wählen → rechts Spiegeln** | zweite Konstruktion |
| Erste Schicht maßhaltig | **Elefantenfuß ausgleichen** aus dem Materialprofil | Slicer-Einstellung, projektfern |
| Toleranz messen statt raten | **Varianten erzeugen** (§28.3) | mehrere Exporte von Hand |
| Eine Passung prüfen, ohne das Teil zu drucken | **Bohrung, Zapfen oder Fläche wählen → rechts Prüfstück erzeugen** | von Hand nachmodellieren |
| Zweifarbige Beschriftung | **Text aufbringen** mit eigenem Filament, oder **Schriftzug als Körper** | zwei Konstruktionen |
| Deckel zu einer vorhandenen Schachtel | **Erzeugen → Bausteine → Deckel erzeugen** | Hohlraum abmessen und neu zeichnen |
| Schraubdeckel für ein Glas oder eine Dose | **Erzeugen → Bausteine → Drehdeckel erzeugen** | Gewindepaar von Hand konstruieren |
| Zehn Stück auf die Platte | **Objekt duplizieren** mit Anzahl | zehnmal kopieren, Stückzahl im Dateinamen |
| 3MF-Baugruppe aus dem Slicer öffnen | **Datei → Modell einfügen** — die Teile kommen einzeln an | pro Teil eine STL exportieren |
| Etwas an eine angeklickte Fläche setzen | **Fläche wählen, Operation aufrufen** — Ort und Achse sind eingetragen | Koordinaten ablesen und eintippen |
| Eine vorhandene Bohrung in STL oder STEP ändern | **Bohrung anklicken → Bohrung ändern** — nur den neuen Durchmesser eintragen | Stopfen bauen, neu bohren oder CAD-Historie rekonstruieren |
| Eine erkannte Bohrung zwei Millimeter versetzen | **Bohrung wählen → rechts Merkmal verschieben**; spätere Änderungen auch im Verlauf | zurücknehmen und neu bohren |
| Dichtung aus TPU im PETG-Gehäuse | **Körper wählen → rechts Material festlegen** | zwei Projekte |

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

Neben dem Netz-Kern steht ein zweiter mit mathematisch beschriebenen Flächen
und Kanten (§30). Er kommt ins Spiel, wenn eine STEP-Datei geladen, ein
exakter Körper angelegt oder ein Netz umgewandelt wird. **Verrunden** und
**Fase anbringen** arbeiten seit 0.4.1 auch an geeigneten Kanten eingelesener
Netze. Auf einem Netz besteht eine Rundung aus kurzen geraden Abschnitten; ein
exakter Körper behält den mathematischen Bogen. Die Auswahl erfolgt in beiden
Fällen im Bild, Radius oder Breite werden rechts eingegeben.

Der Objektbaum kennzeichnet exakte Körper. *Flächenbearbeitung beenden* macht
aus einem exakten Körper jederzeit ein Netz; der Schritt steht im Verlauf, ein
Undo holt den exakten Körper zurück. In die andere Richtung baut *In Flächen
und Kanten umwandeln* aus einem Netz einen Körper aus Ebenen, Zylindern,
Kegeln, Kugeln und Ringen. Einen Konstruktionsverlauf bekommt er dabei nicht;
den stellt *Modell nachbauen* als Folge von Operationen auf, wo es einen
Aufbau findet, und sagt es, wenn es keinen findet.

Exportiert wird ein solcher Körper als `STEP` mit Flächen und Kanten; STL und
3MF bleiben für alles, was auf den Drucker soll. Jedes Installationspaket
bringt den Kern mit.

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

**Automatisch teilen** (rechts am gewählten Körper, unter *Vorbereiten*) schneidet
ein Objekt, bis jedes Stück auf die Platte passt. Die Trennebene wird gesucht, nicht geraten: über dieselbe
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

Zugewiesen wird nach Auswahl des Körpers oder einer erkannten Fläche über
die Filamentauswahl rechts im Fenster. Die
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

---

## Für Entwickler

Welche Unterlage welche Frage beantwortet — Bauplan, Hausordnung, Roadmap,
Konzepte, Karten —, steht in [CLAUDE.md](CLAUDE.md), die Regeln in
[AGENTS.md](AGENTS.md). Dort stehen auch die Befehle für betroffene Tests,
Entwicklungstor, Release-Suite und Start.

### Einrichten

Entwickelt wird mit CPython 3.14, die Pakete baut die CI mit 3.14.8. Die
3D-Ansicht zeichnet mit pygfx über wgpu.

```
python -m venv .venv
.venv/Scripts/python.exe -m pip install -c constraints.txt -e ".[dev,geom,ui,brep]"
git config core.hooksPath .githooks
```

Die dritte Zeile ist einmal je Arbeitsplatz nötig und schaltet die Git-Hooks des
Projekts ein: `pre-commit` prüft Bezeichner und neue Übersetzungstexte,
`commit-msg` die Umlautschreibung der Commit-Meldung, `post-commit` pusht jeden
Commit sofort. Ohne die Zeile fehlen diese Prüfungen und der automatische Push.
`core.hooksPath` ist eine lokale Einstellung; Git holt sie sich nicht aus dem
Repository, deshalb steht sie hier und nicht in einer Datei.

Ohne das Extra `brep` fehlt der exakte Kern; die betroffenen Operationen sagen
das in einem Satz, alles andere funktioniert unverändert. Zum Starten per
Doppelklick liegt unter `tools/start-solidon3d.cmd` eine Verknüpfung.

Je Änderung laufen die betroffenen Tests, vor einem Commit das Entwicklungstor
aus Suite, Ruff, Formatprüfung und mypy. Fenster-, Renderer- und
Leistungsprüfungen laufen ausschließlich beim Release; die Release-CI fährt die
Fensterdateien unter Windows und die Rendererprüfungen ohne Fenster auf allen
vier Paketplattformen.

### Lokale Sprachmodelle messen

Ob ein Modell die Werkzeuge wirklich aufruft, misst
`.venv/Scripts/python.exe tools/check_local_model.py qwen3:14b`; wie gut es mit
den Referenzanfragen zurechtkommt,
`.venv/Scripts/python.exe tools/run_agent_suite.py --backend ollama`.

Die Suite-Spalte der Modelltabelle stammt vom 26.09.2026, auf freier Karte
(RTX 4080). Derselbe Stand mit dem ganzen Werkzeugsatz statt des Angebots traf
mit `qwen3:14b` im selben Fenster 14 von 39, neunmal riss dabei das Fenster;
mit einem Fenster von 40 960 Token 24 von 39, aber in 149 statt 47 Minuten und
zu einem Zehntel auf dem Prozessor.

### ComfyUI aus dem Entwicklungsbaum

`.venv/Scripts/python.exe tools/setup_comfyui.py` richtet ein, was der Dialog
*Modelle einrichten …* einrichtet. Die Arbeit steckt in
`app/core/backends/comfy_setup.py`; sie reist im Paket mit. Welche Knoten ein
Ablauf benutzt, steht in `app/core/backends/data/text_to_image.json` und
`image_to_mesh.json` (der Weg aus Text fährt beide nacheinander); ändert sich ComfyUI, erneuert
`tools/comfy_node_info.py` die Knotenbeschreibung, gegen die die Suite beide
Abläufe prüft. Die Dateien nennen Rollen und keine Dateinamen: Für einen
anderen Generator wird die Datei ersetzt, nicht der Quelltext.

### Paketieren

Reihenfolge und Voraussetzungen für einen beauftragten Release stehen in
[Erzeugen](.claude/skills/erzeugen/SKILL.md), die Übergabe der
Windows-Signatur in [Signierung/README.md](Signierung/README.md). Die Bauläufe
für Windows, Linux und beide Mac-Architekturen stehen in
`.github/workflows/build.yml`; sie laufen erst, wenn die Suite auf den
vorgesehenen Plattformen grün ist. Für Windows wird nur die signierte
Setup-Datei mit der signierten Anwendung veröffentlicht: `tools/sign_release.py`
holt die prüfsummengebundene Anwendung aus dem Baulauf und signiert sie mit dem
Certum-Zertifikat, `.github/workflows/windows-signed-installer.yml` baut daraus
den Installer, und das Werkzeug signiert und prüft danach die Setup-Datei.

Ein lokaler Probe- oder Ersatzbau verwendet einen eigenen Arbeitsbaum mit
passender Entwicklungsumgebung und C-Compiler. Vor PyInstaller werden der
Schichtkern und das Prüfmodul mit seinem signierten Manifest aus demselben
Stand gebaut:

```
.venv/Scripts/python.exe -m pip install -c constraints.txt pyinstaller cython setuptools
.venv/Scripts/python.exe tools/build_slice_core.py
.venv/Scripts/python.exe tools/build_licence_module.py
.venv/Scripts/pyinstaller.exe packaging/solidon3d.spec --noconfirm
```

Ergebnis ist ein Ordner unter `dist/Solidon3D`. `tools/make_linux_packages.py`
macht daraus unter Linux AppImage und Flatpak; Menüeintrag, Flatpak-Manifest
und AppStream-Beschreibung schreibt es aus den Werten in `app/branding.py`,
mit `--files` nur diese und ohne Linux. Das tar.gz des Baus bleibt ein
Bauartefakt. `appimagetool` und `flatpak-builder` sind externe Programme und
werden nicht mitgeliefert (§36).
