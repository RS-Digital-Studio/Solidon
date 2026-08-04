# Konzept — SindriCAD als Maßstab

Anlass sind vier Fundstellen zu **SindriCAD**, einem freien parametrischen
CAD-Programm für den 3D-Druck, das am 2. August 2026 als öffentliche Beta
erschienen ist. Die Frage dahinter: *sowas wollen wir auch.*

Dieses Dokument beantwortet sie in drei Schritten — was SindriCAD wirklich
ist, was Formwerk heute wirklich ist, und was aus dem Unterschied folgt. Es
ist eine Konzeptvorlage, keine Arbeitsliste: was daraus beschlossen wird,
wandert nach `ROADMAP.md`.

**Verhältnis zu `konzept-bedienung.md`:** Jenes Dokument ist die Durchsicht
der eigenen Oberfläche. Dieses schaut nach außen. Wo beide dieselbe Lücke
finden, steht sie **dort** und wird hier nur bestätigt — nicht wiederholt
(Doku-Doktrin, Regel 3).

---

## Teil 1 — Was SindriCAD ist

### 1.1 Herkunft und Technik

Ein Einzelprojekt des Machers hinter TinkerAtlas (Pseudonym *MakerViking*),
entstanden aus einem konkreten Ärger: das professionelle CAD des Entwicklers
lief nicht unter Linux, Wine war brüchig, eine VM ohne Grafikkarte zu langsam.
Statt den Arbeitsablauf zu verbiegen, wurde das Werkzeug gebaut. Der Name
kommt von Sindri, dem Zwergenschmied der nordischen Mythologie.

| | |
|---|---|
| Kern | **build123d** über **OpenCASCADE** — B-Rep, kein Mesh-Kern |
| Oberfläche | **Tauri** (Rust-Rahmen, Web-Frontend) |
| Plattformen | Linux, Windows, macOS |
| Lizenz | **AGPL**, quelloffen |
| Zugang | kein Konto, kein Abo, keine Testfrist |
| Stand | öffentliche Beta, unsignierte Builds |

Bemerkenswert an der Technik: SindriCAD **ist** im Kern das, was der Bauplan
als zweiten Konstruktionskern beschreibt (§30) — build123d über OpenCASCADE,
genau die dort genannte Option. Formwerk hat diesen Kern seit P12, aber als
*zweiten* neben dem Mesh-Kern. SindriCAD hat nur diesen einen.

### 1.2 Funktionsumfang, wie beworben

* **Volumenmodellierung:** Extrudieren, Rotieren, Loften, Verrunden, Fasen,
  Aushöhlen, Press/Pull, Spiegeln, Muster
* **Parametrische Historie:** jeder Schritt editierbar, benannte Parameter,
  echte Maße — eine Bemaßung ändern, das Teil baut sich neu auf
* **Skizzen** mit Bemaßungen und Zwangsbedingungen
* **Oberflächentexturen als echte Geometrie:** Rändel, Waben, Wellen,
  Voronoi-Zellen — kein Bump-Map, überlebt den Slicer
* **Mehrfarb-Ausgabe** über 3MF, das ein Mehrfarbdrucker versteht
* **Messwerkzeuge** und **Schnittansichten** zum Prüfen von Wandstärke und
  Spiel vor dem Druck
* **Formate:** STL, STEP, 3MF hinaus — STEP, BREP, STL, 3MF, OBJ, GLB herein
* **Vertraute Tastenkürzel** aus gängigem professionellem CAD
* **Snapmaker U1:** Mehrmaterial an OrcaSlicer übergeben, G-Code über das
  lokale Netz an den Drucker schicken

### 1.3 Die Positionierung — der eigentliche Inhalt

Drei Sätze tragen den ganzen Auftritt, und keiner davon ist eine Funktion:

1. **„Es fühlt sich vertraut an."** Abläufe und Kürzel wie im großen CAD. Wer
   Fusion kennt, kennt das hier.
2. **„Es ist für den Druck gebaut, nicht für technische Zeichnungen."**
   Skizzieren → Volumen ziehen → Kanten runden → Textur eindrücken → an den
   Slicer. Das ist derselbe Satz, den Formwerks §2.2 als Weg 2 beschreibt.
3. **„Es kann dir nicht weggenommen werden."** AGPL, kein Konto, kein Abo.

Dazu eine radikal offene Finanzierung: 335 $ im Monat Sockelkosten, 19 % des
Ziels erreicht, ein Monat ohne Entwicklung, weil die Werkzeuge unbezahlt
blieben, 99 $ für das Apple-Entwicklerkonto als benannter Engpass. Ehrlichkeit
als Marketing — und es funktioniert.

### 1.4 Das Umfeld, in dem das erscheint

Aus der Software-Rubrik von 3Druck.com, dieselbe Woche:

* **FreeCAD mit MCP-Schnittstelle** — FreeCAD lässt sich über das Model
  Context Protocol von Claude oder ChatGPT steuern. Dokumente anlegen, Körper
  hinzufügen, Maße ändern, Python ausführen.
* **Prusa EasyPrint** — Abo-Modell für den Cloud-Slicer, öffentliche Kritik,
  der Firmengründer musste reagieren.
* **Hi3D, Modly, Meshy, Tripo** — KI-Modellerzeugung, teils mit
  Milliardenfinanzierung.
* **FilaSim, PanX** — Simulation von Belastung und Restspannung.
* **Watchtower** — lokales Druckerfarm-Dashboard *ohne Cloud*.

Zwei Signale zählen für uns. Erstens: **die KI-gesteuerte CAD-Bedienung ist
kein Alleinstellungsmerkmal mehr** — FreeCAD hat sie, wenn auch angeflanscht.
Der Bericht nennt die Grenze deutlich: Primitive, Booleans und Muster gehen,
stark bedingte Skizzen und Verrundungsketten kaum; brauchbar als schneller
Entwurfspartner, nicht bei toleranzkritischen Teilen. Genau diese Grenze
adressiert Formwerks Leitprinzip 5 (die KI erzeugt niemals Koordinaten,
sondern verweist auf Features, Parameter und geprüfte Bausteine) — aber das
weiß nur, wer es liest. Zweitens: **lokal und ohne Abo ist gerade ein
Verkaufsargument**, kein Verzicht.

---

## Teil 2 — Kontrolle: der Stand von Formwerk

Gemessen am 4. August 2026, Commit `088aefe`.

### 2.1 Umfang

| | |
|---|---|
| Anwendung | 178 Python-Dateien, 51.565 Zeilen |
| Tests | 95 Dateien, 25.678 Zeilen |
| Registrierte Operationen | **61** |
| Registrierte Bausteine | **16** |
| Texturmuster | **8** |
| Oberflächenmodule | 35 |
| Phasen | P0 bis P15, Arbeitsliste bis auf einen Punkt abgetragen |

### 2.2 Das Tor

| Prüfung | Ergebnis |
|---|---|
| `ruff format --check` | 326 Dateien formatiert |
| `mypy` | keine Beanstandung in 178 Quelldateien |
| `ruff check` | **1 Befund** — siehe 2.3 |
| `pytest` | **2579 grün, 1 rot** in 3:30 min — siehe 2.3 |

### 2.3 Drei Befunde aus der Kontrolle

**Der ruff-Befund gehört nicht uns.** `app/ui/viewport.py:17` importiert
`QEvent`, ohne es zu benutzen. Die Datei ist ungestaged um 163 Zeilen
gewachsen — eine **parallele Sitzung** arbeitet gerade daran. Nicht angefasst;
sie räumt das mit ihrem eigenen Commit auf.

**Der rote Test gehört ebenfalls nicht uns.**
`test_translations.py::test_every_text_is_translated[en]` meldet drei
**verwaiste** englische Einträge: *Entfernt*, *Hinzugefügt*, *Unverändert*.
Nicht fehlende Übersetzungen, sondern übrig gebliebene — die parallele Sitzung
hat die zugehörigen Oberflächentexte entfernt und den Katalog noch nicht
nachgezogen. Ebenfalls nicht angefasst. **Bis das behoben ist, ist das Tor
rot** (`AGENTS.md`: rot heißt nicht fertig) — der Stand aus 2.1 und 2.2 ist
davon unberührt, weil kein Sachtest betroffen ist.

**Ein erster Testlauf brach mit einem nativen Stapelabzug ab.** Kein
Testfehler, sondern ein Absturz des Prozesses. Das ist das bekannte Bild aus
`konzept-bedienung.md` 5.5 — die Referenzschleife zwischen Python und VTK, dort
als behoben verzeichnet. Zwei spätere Läufe liefen durch. **Das heißt: der
Absturz ist selten, nicht weg.** Er verdient eine eigene Zeile in der Roadmap,
unabhängig von diesem Konzept: ein Absturzprotokoll, das ihn beim nächsten Mal
festhält, steht dort ohnehin noch offen.

---

## Teil 3 — Der Abgleich

### 3.1 Wo Formwerk gleichauf oder weiter ist

Das ist der größere Teil der Tabelle, und er ist die eigentliche Nachricht
dieses Dokuments.

| SindriCAD | Formwerk |
|---|---|
| Extrudieren, Rotieren, Loften | `sketch_extrude`, `sketch_revolve`, `sketch_loft` — dazu `sketch_sweep`, das SindriCAD nicht nennt |
| Verrunden, Fasen, Aushöhlen | `fillet_edges`, `chamfer_edges`, `shell_exact` gegen den B-Rep-Kern, dazu `draft_faces`, `thread_exact` |
| Press/Pull | `push_face`, Kürzel `Q`, Gizmo an der gewählten Fläche |
| Spiegeln, Muster | `mirror_object`, `pattern` |
| Parametrische Historie | Op-Stack, non-destruktiv (Leitprinzip 2), Undo auf Transaktionsebene |
| Benannte Parameter | Projektparameter §13 mit **eigener Grammatik ohne `eval`** (Regel 10) |
| Zwangsbedingungen | 9 Bedingungen, eigener 2D-Solver auf scipy, Vollbestimmtheit wird erkannt und benannt |
| Texturen: 4 Muster | **8 Muster** — `rib`, `wave`, `knurl_straight`, `knurl_diamond`, `hexagon`, `dimple`, `voronoi`, `noise` |
| Mehrfarbe über 3MF | `assign_slot`, `paint_slot`, `slots_from_texture`, 3MF mit Farbgruppen (§29) |
| Messen, Schnitt | beides vorhanden, dazu Explosions- und Analyseleisten |
| Import STEP/BREP/STL/3MF/OBJ/GLB | dieselben **plus** PLY, OFF, GLTF, SVG, DXF |
| Export STL/STEP/3MF | dieselben plus OBJ, mit Exportprüfung als Bericht statt Blockade (§29) |
| Ein Slicer (Orca) | **drei** — Prusa, Orca, Cura, mit Rückprüfung der geschriebenen Werte |
| Vertraute Kürzel | `shortcut_schemes.py` mit Fusion-Belegung — **aber nur fürs Modellieren**, siehe 3.2 |

### 3.2 Wo SindriCAD gewinnt

Vier Punkte. Drei davon sind keine Geometriefragen.

1. **Die Skizze ist bedienbar, nicht nur rechenbar.** Ändern-Gruppe (Trimmen,
   Verlängern, Versetzen, Spiegeln, Muster), Projizieren,
   Konstruktionsgeometrie, Zeichenkürzel, Ursprung und Maßstab im Bild.
2. **Die Texturen sind sichtbar.** Bei SindriCAD sind sie das Aushängeschild
   mit eigenem Bild und eigenem Absatz. Bei uns sind sie ein Auswahlwert einer
   Operation.
3. **Das Teil verlässt das Programm als Druck, nicht als Datei.** G-Code über
   das lokale Netz an die Maschine.
4. **Es gibt SindriCAD in der Öffentlichkeit.** Binnen eines Tages: 3Druck.com
   deutsch und englisch, TinkerAtlas, Tao of Mac, mehrere Fachkonten.

### 3.3 Was Formwerk hat, das SindriCAD nicht hat

Der Vollständigkeit halber, weil es die Größenordnung klarstellt:

* **Die Agentenschicht** (§26) — Vorschlag als eine Transaktion, Prüfungen
  nach jeder Op, Regelsammlung, Agenten-Suite. FreeCAD hat MCP angeflanscht;
  hier ist es der Aufbau.
* **MCP-Server im Fenster** — Formwerk lässt sich fernsteuern, jeder Fernaufruf
  geht denselben Weg durch `History.apply` und trägt seine Herkunft.
* **Die Schichtanalyse** (§22) — Überhänge, Inseln, Stützvolumen,
  Brückenweiten, Orientierungssuche. SindriCAD hat davon nichts.
* **Bausteinbibliothek und Normteile** (§24) — Schraubenlöcher, Heatsets,
  Mutternfallen, Magnettaschen, Schnappverbindungen, Filmscharniere, gedruckte
  Gewinde, Kabelverschraubungen.
* **Materialprofile und Toleranzen als Verweis** (`auto:<material>`, Regel 7)
  samt Selbstkalibrierung (§28.3).
* **Auto Split mit Verstiftung**, Passungen, Prüfbericht.
* **Handbuch, sieben Touren, Website, Installationsdatei.**

**Fazit des Abgleichs:** SindriCAD ist funktional weitgehend eine Teilmenge
von Formwerk. Es gewinnt dort, wo Formwerk seine eigene Substanz nicht
einlöst — in der Bedienung, in der Sichtbarkeit, in der letzten Meile zum
Drucker.

---

## Teil 4 — Die Befunde

### B1 — Die Skizze ist rechnerisch fertig und bedienerisch halb

**Steht bereits vollständig in `konzept-bedienung.md`, Teil 4**, mit neun
konkreten Punkten und einer Gegenüberstellung mit Fusion. SindriCAD bestätigt
sie unabhängig: was dort als Lücke notiert wurde — Ändern-Gruppe, Projizieren,
Zeichenkürzel, Ursprung und Maßstab — ist bei SindriCAD Grundausstattung.

**Was dieses Dokument hinzufügt:** nichts an der Liste. Nur die Einordnung,
dass diese neun Punkte keine Politur sind, sondern der Abstand zum Wettbewerb.
Sie gehören nach oben.

### B2 — Acht Texturmuster, die niemand sieht

Formwerk hat **doppelt so viele Muster wie SindriCAD** und behandelt sie als
Parameter einer Operation. SindriCAD hat vier und macht daraus ein
Alleinstellungsmerkmal mit Bild, Absatz und Bewegtbild.

Kein Funktionsproblem. Ein Darstellungsproblem — und das ist bei
gleichwertiger Substanz das teurere.

### B3 — Die letzte Meile zum Drucker fehlt

Formwerk kommt weit: Exportprüfung, Slicer-Profil, Aufruf von Prusa, Orca oder
Cura, Rückprüfung der geschriebenen Werte, G-Code zurücklesen (§28.1). Dann
hört es auf. Die Datei liegt im Ordner.

**Der Bauplan kennt diese Strecke nicht.** §28 heißt „Rückkopplung aus Slicer
und Drucker", meint mit „Drucker" aber das Zurücklesen und das Nachmessen
gedruckter Testkörper — nicht das Senden. §29 endet beim Slicer-Aufruf. Eine
Erweiterung hier ist eine **Bauplanänderung und braucht Ansage.**

Abgrenzung, damit kein Missverständnis entsteht: G-Code **senden** ist kein
G-Code **erzeugen**. Der eigene Slicer bleibt ausgeschlossen (§41, AGENTS.md).

### B4 — GLB kommt herein und nicht heraus

`READABLE_SUFFIXES` liest `.glb` und `.gltf`; `writer.py` schreibt `stl`,
`3mf`, `obj`, `step`. SindriCAD schreibt GLB. Nutzen: Vorschau und Weitergabe
ohne CAD-Programm. Kleiner Punkt, kleine Arbeit.

### B5 — Es gibt uns nicht, solange niemand über uns schreibt

SindriCAD stand binnen eines Tages in der deutschen und englischen Fachpresse.
Formwerk ist fertiger und unbekannt. Dieser Befund ist keine Technikfrage, und
er hängt an einer Entscheidung, die nicht in diesem Dokument fällt — siehe
Teil 8.

---

## Teil 5 — Was wir ausdrücklich nicht übernehmen

| Nicht übernehmen | Warum |
|---|---|
| **Nur ein B-Rep-Kern** | Der Mesh-Kern trägt Weg 1 (fremdes STL anpassen) und Weg 3 (generieren). §30: zweiter Kern **neben**, nicht als Ersatz. |
| **Tauri / Web-Frontend** | PySide6 steht, der Kern ist qt-frei (Regel 1). Ein Rahmenwechsel wäre ein Neubau ohne Gegenwert. |
| **Snapmaker-U1-Sonderweg** | Ein Gerät bevorzugen widerspricht dem Profilgedanken (§38). Wenn Senden, dann über ein offenes Protokoll für viele Maschinen. |
| **Spendenfinanzierung mit offenen Zahlen** | Passt zu einem Einzelprojekt mit Gemeinschaft, nicht zu RS Digital. |
| **Unsignierte Builds** | Wir haben eine Installationsdatei. Signatur ist bei uns eine Aufgabe, kein Bettelbrief. |
| **Eigener G-Code-Slicer** | §41 und AGENTS.md, unverändert. |

---

## Teil 6 — Das Konzept

Vier Bausteine. Jeder hat ein Ziel, einen Umfang und ein Abnahmekriterium.
Baustein A ist bereits beschlossene Arbeit und wird hier nur eingeordnet.

### Baustein A — Die Skizze fertig bedienen

**Ziel:** Wer aus Fusion kommt, zeichnet in Formwerk eine Kontur, ohne
nachzuschlagen.

**Umfang:** unverändert die neun Punkte aus `konzept-bedienung.md` Teil 4. Sie
werden hier **nicht wiederholt**, sondern höher gewichtet: die Punkte 1, 2, 3
(Ursprung/Achsen, Zeichenkürzel, kontextabhängige Belegung) sind der billigste
sichtbare Gewinn im ganzen Programm; die Punkte 4 und 5 (Trimmen/Versetzen und
Projizieren) sind der Funktionsabstand.

**Bauplanlage:** §30.1 nennt als Grund für diese Stufe ausdrücklich eine
Produktentscheidung — *so wenig Fremdprogramme wie möglich*. Genau das ist
SindriCADs Versprechen. Die Skizze halb zu lassen, hebt diese Entscheidung
praktisch auf.

**Abnahme:** Eine Kontur, die nicht aus einer Grundform kommt, entsteht ohne
Handarbeit an Punktlisten — Linie, Trimmen, Versetzen, Bemaßung, fertig. Der
Ablauf ist eine Tour und läuft offscreen im Test.

### Baustein B — Die Texturen ans Licht

**Ziel:** Was wir doppelt so gut können wie der Wettbewerb, sieht man, bevor
man es sucht.

**Umfang:**

1. **Musterkatalog mit gerenderten Vorschaubildern** — acht Kacheln statt
   einer Auswahlliste. Die Bilder werden gerendert, nicht gepflegt (Regel 7
   der Baustein-Checkliste); `figures.py` kann das bereits.
2. **Eine Handbuchseite** „Griff und Muster", die zeigt, dass die Textur echte
   Geometrie ist und den Slicer unverändert übersteht — der Satz, mit dem
   SindriCAD wirbt, gilt bei uns genauso und steht nirgends.
3. **Eine Tour**, die eine Textur auf eine Fläche bringt. Die sieben
   vorhandenen sind laut Durchsicht „inhaltlich vorbildlich" — die achte
   schließt an.
4. **Ein Beispielprojekt** mit Textur, das auf dem Startbildschirm liegt.

**Abnahme:** Die acht Muster sind ohne Handbuch auffindbar und ohne
Probedruck unterscheidbar. Kein Bild ist von Hand gepflegt.

### Baustein C — Die letzte Meile zum Drucker

**Ziel:** Vom fertigen Teil zum laufenden Druck, ohne den Dateimanager.

**Umfang** — bewusst klein und offen gehalten:

1. **Ein Protokoll, nicht ein Gerät.** Moonraker (Klipper) und OctoPrint
   decken den Selbstbau- und Bastelbereich ab; herstellereigene Netzwege
   bleiben außen vor, solange sie kein offenes Protokoll haben. Der Elegoo
   Centauri Carbon 2 als Referenzmaschine entscheidet, was zuerst gebaut wird.
2. **Der Drucker ist ein Profileintrag** (§38), keine Sonderfunktion — Adresse
   und Zugangsschlüssel gehören zum Druckerprofil, nicht ins Projekt.
3. **Senden ist eine Handlung, keine Op.** Es ändert keine Geometrie (Regel 2)
   und gehört nicht in den Stack — dieselbe Einordnung wie der Slicer-Aufruf.
4. **Kein Netz, kein Problem** (Leitprinzip 8): fehlt der Drucker, sagt die
   Oberfläche das in einem Satz und der Export bleibt, wie er ist.
5. **Fehler als Vorschlag** (Regel 17): „Drucker antwortet nicht" nennt die
   Adresse und bietet das Speichern auf Karte an.

**Bauplanlage:** **Erweiterung von §28 nötig.** Vorschlag für einen neuen
§28.4 „G-Code an die Maschine" mit den fünf Punkten oben. Wird nicht ohne
Zustimmung geschrieben.

**Abnahme:** Ein Teil geht von der Exportprüfung bis zum bestätigten
Auftrag auf der Maschine, ohne dass eine Datei von Hand angefasst wird. Ohne
erreichbaren Drucker verhält sich alles wie heute.

### Baustein D — GLB hinausschreiben

**Ziel:** Ein Teil lässt sich weitergeben, ohne dass der Empfänger CAD hat.

**Umfang:** `glb` in die Formattabelle von `writer.py`, Farbgruppen mitgeben,
soweit das Format sie trägt. Ein Format, kein Konzept.

**Abnahme:** Export als GLB, Rückimport in Formwerk, gleiche Objektzahl und
Maße innerhalb `EPS_GEOM`.

---

## Teil 7 — Reihenfolge

| | Baustein | Warum dort |
|---|---|---|
| 1 | **A** — Skizze (Punkte 1–3 aus Teil 4) | Billigster sichtbarer Gewinn. Ursprung, Achsen, Zeichenkürzel. Tage, nicht Wochen. |
| 2 | **B** — Texturen ans Licht | Vorhandene Substanz sichtbar machen ist immer billiger, als neue zu bauen. |
| 3 | **A** — Skizze (Punkte 4–5) | Trimmen, Versetzen, Projizieren. Das ist der echte Funktionsabstand und braucht Zeit. |
| 4 | **D** — GLB | Klein, passt zwischen zwei größere Sachen. |
| 5 | **C** — letzte Meile | Braucht zuerst die Bauplanentscheidung, dann eine echte Maschine zum Prüfen. |

Baustein B vor A(4–5): Wer wenig Zeit hat, macht zuerst sichtbar, was fertig
ist, und baut dann, was fehlt.

---

## Teil 8 — Die offene Entscheidung

Alles oben ist Technik und liegt in unserer Hand. Befund **B5** liegt es
nicht.

SindriCAD wirbt mit drei Sätzen: **kein Konto, kein Abo, AGPL — es kann dir
nicht weggenommen werden.** Formwerk erfüllt die ersten beiden mühelos
(Leitprinzip 8: vollständig ohne Konto und ohne Netz nutzbar). Beim dritten
steht in `LICENSE`: *Copyright (c) 2026 RS Digital. Alle Rechte vorbehalten.*
Proprietär, mit zwei MIT-Ausnahmen für die Bausteinbibliothek und den
Referenzkorpus — die klug gewählt sind, weil ihr Inhalt in den Ergebnissen der
Nutzer landet.

Das ist kein Fehler und wird hier nicht als einer behandelt. Aber es
entscheidet, was „sowas wollen wir auch" heißen kann:

* **Bleibt Formwerk proprietär**, sind die Bausteine A bis D die vollständige
  Antwort. Die Fachpresse berichtet dann über ein gutes Programm, nicht über
  ein freies — das geht, verlangt aber einen anderen Aufhänger. Der stärkste
  wäre: *lokal, ohne Abo, mit Agent, der keine Koordinaten erfindet* — genau
  die Grenze, an der FreeCADs MCP-Anbindung scheitert.
* **Wird über die Lizenz neu nachgedacht**, ist das eine Geschäfts- und keine
  Konstruktionsentscheidung, und sie fällt nicht in diesem Dokument.

**Diese Frage bleibt offen und wird nicht stillschweigend beantwortet**
(Regel 21). Die Bausteine A bis D sind von ihr unabhängig und können sofort
beginnen.
