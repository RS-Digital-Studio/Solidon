# Konkurrenz und Website — Stand 17.10.2026

Recherche für Robert, unverändert abgelegt; Zeilen- und Messangaben gelten für den 17.10.2026.

**Auftrag Robert (17.10.2026):** „wir wollen die hochwertigste webseite haben von allen und bis
1.0 auch die beste app“; die Lücken der App werden alle behoben, in den Phasen des Programms
(`.claude/.state/programm-2026-10/STAND.md`). **Entscheidungen Robert zu (E) und (F):** ab dem
01.12.2026 **kein kostenloser Einstieg** (keine Testphase, keine Geld-zurück-Zusage, keine freie
Stufe) — Empfehlung E1 und F2 entfallen, die Website überzeugt bis zum 30.11. über die Demo und
danach über Belege; **KI ohne eigene Einrichtung (gehostet) erst nach 1.0** (P11). Umsetzung:
Website [RM-822](../ROADMAP.md#rm-822), App [RM-818](../ROADMAP.md#rm-818) bis
[RM-821](../ROADMAP.md#rm-821).

**Quellenlage.** „3druck.de“ antwortet nicht (HTTP 503, Zertifikat für
kasserver.com, gemessen 17.10.2026); das Fachportal ist **3Druck.com**. Gelesen
wurde dessen Software-Rubrik über den Feed, Seiten 1–8, also 144 Artikel vom
12.06. bis 16.10.2026. Davon waren 45 einschlägig, 40 sind im Volltext
ausgewertet. Die Herstellerseiten wurden am 17.10.2026 abgerufen, dazu
Bildschirmfotos bei 1440 px. Bambu Lab, MakerWorld, Tripo und Autodesk sperren
den automatischen Abruf (Cloudflare bzw. Akamai). Das wurde nicht umgangen,
dort tragen Sekundärquellen. solidon3d.de ist live gemessen (Puppeteer, 390 px
und 800 px). Die Live-Seite entspricht dem Arbeitsbaum, im Download-Kasten
steht noch 0.6.0.

**Zwei Funde vorab.** 3Druck.com hat zweimal über Solidon berichtet, sachlich
und mit benannten Grenzen ([23.08.2026](https://3druck.com/programme/solidon3d-desktop-software-passt-heruntergeladene-stl-dateien-ohne-cad-an-13162117/),
[02.10.2026](https://3druck.com/programme/update-fuer-solidon3d-stl-bearbeitung-erkennt-bohrungen-und-oberflaechenmuster-06163581/)).
Die Website nennt das nirgends. In den beiden Übersichten der Redaktion
([25 kostenlose Tools, 02.09.](https://3druck.com/programme/kostenlose-tools-3d-druck-uebersicht-44162321/),
[23 KI-Tools, 31.08.](https://3druck.com/programme/ai-generatoren-3d-modelle-uebersicht-39120212/))
fehlt Solidon.

---

## (A) Konkurrenz aus 3Druck.com, Juni bis Oktober 2026

Datum = Artikeldatum; die Verweise führen auf den Artikel. „n. g.“ = im Artikel
nicht genannt; Ergänzungen von der Herstellerseite (abgerufen 17.10.) sind
markiert (H).

### Fremde STL anpassen, Netz zu CAD

| Datum | Programm (Hersteller) | Überschneidung mit Solidon | Preis / Lizenz | Plattform |
|---|---|---|---|---|
| 11.10. | [ShapeAnywhere](https://3druck.com/programme/shapeanywhere-browser-cad-soll-stl-modelle-wieder-bearbeitbar-machen-09163883/) (n. g.) | Direktmodellierung; Mesh→CAD in Arbeit: erkennt Flächen, Bohrungen, Rundungen, Fasen | Gast und Konto gratis, Mesh→CAD als bezahlte Beta (H) | Browser, deutsche Seite (H) |
| 13.10. | [stl2step](https://3druck.com/programme/stl2step-freie-software-wandelt-stl-netze-in-step-volumenkoerper-um-00163977/) (BlinkingSun) | STL→STEP, erkennt Ebenen, Zylinder, Verrundungen, repariert | MIT, gratis | Win, Mac, Linux |
| 06.10., 21.09., 05.08. | [Backflip AI](https://3druck.com/programme/backflip-ai-mark3d-vertreibt-ki-software-fuer-reverse-engineering-in-europa-52163680/) (Backflip, EU-Vertrieb Mark3D) | Scan, Netz, Zeichnung oder Foto → parametrisches CAD mit Feature-Baum | n. g.; laut Artikel 21.09. höchstens 10 $ Aufwand je Teil | Fusion-Add-in und Web-App (H) |
| 14.10. | [Creallo Atlas](https://3druck.com/programme/creallo-atlas-kostenloser-3d-viewer-prueft-modelle-lokal-und-schaetzt-fertigungskosten-50163989/) (Creallo, Südkorea) | 13 Formate, Messen, Wandstärkenkarte, Schnitt, Autofix, Richtpreise | gratis; Konto für Reparatur und Teilen (H) | Win, Mac, Linux, offline |
| 15.09. | [Forma3D](https://3druck.com/programme/forma3d-mesh-editor-fuer-iphone-und-ipad-exportiert-farbige-3mf-dateien-06162946/) (n. g.) | Netz bearbeiten, Boolesch über Manifold, Flächen einfärben, farbiges 3MF | n. g. | iPhone, iPad |

### Konstruieren ohne CAD, parametrisch

| Datum | Programm (Hersteller) | Überschneidung mit Solidon | Preis / Lizenz | Plattform |
|---|---|---|---|---|
| 07.09., 09.09. | [Constructor AI](https://3druck.com/programme/constructor-ai-3d-modelle-per-textbeschreibung-statt-cad-zeichnung-38162681/) (Essen) | Teil beschreiben, Programm fragt nach Maßen; STL-Import, Bohrungen, Gewinde, Relief, Figur aus Foto, G-Code, Direktdruck (H) | **Windows 139 € einmalig**, ein Rechner, offline nach Aktivierung; online ab 4,99 €/24 h (H) | Windows, Browser |
| 01.10. | [OwlCAD](https://3druck.com/programme/owlcad-parametrisches-cad-im-browser-mit-ki-modus-und-mcp-server-fuer-agenten-03163524/) (Spare Matter) | Skizzen, Sweep/Loft, 33 Generatoren (Zahnrad, Gewinde, Gridfinity), Überhang-, Wand- und Dichtheitsprüfung, Ausrichten, Masse und Kosten, KI mit Undo, MCP mit 29 Werkzeugen | Editor gratis, Pro 12 $/Monat oder 120 $/Jahr | Browser |
| 11.10., 16.10. | [SolveCraft → SolidCraft 0.14](https://3druck.com/programme/solidcraft-open-source-cad-oeffnet-in-version-0-14-0-dateien-aus-freecad-und-rhino-13164153/) (Tangency Labs) | Fusion-artige Zeitleiste, Baugruppen, Blech, Zahnräder, FreeCAD-/Rhino-Import, MCP, KI-Chat | MIT oder Apache-2.0, gratis | Win, Mac, Linux, FreeBSD, Browser |
| 03.08. | [SindriCAD](https://3druck.com/programme/sindricad-freies-parametrisches-cad-programm-fuer-den-3d-druck-31161393/) (TinkerAtlas) | Parametrik für den Druck, Gewinde ISO/UNC/UNF/Trapez (H), Texturen als Geometrie, Mehrfarben-3MF (H) | AGPL, gratis | Win, Mac (nur Apple Silicon), Linux, unsigniert |
| 17.09. | [layerling](https://3druck.com/programme/layerling-kostenlose-tinkercad-alternative-laeuft-ohne-anmeldung-im-browser-26163066/) (Formsmith; Fork von [SketchForge](https://3druck.com/programme/sketchforge-open-source-tool-fuer-den-3d-druck-als-alternative-zu-tinkercad-22160256/), 15.07.) | Tinkercad-artig, Fase, Verrundung, Skizzen, Gewinde, Zahnräder, MCP (H) | AGPL, gratis, ohne Konto | Browser, DE/EN |
| 12.10. | [CADlingo 2.0](https://3druck.com/programme/cadlingo-2-0-ki-dienst-erstellt-mehrteilige-cad-modelle-aus-textbeschreibungen-und-exportiert-einzelteile-10163938/) (WeeklyVentures) | Text → parametrisches, mehrteiliges CAD; **fragt bei fehlenden Angaben nach** | STL gratis, STEP bezahlt | Browser |
| 15.10. | [SlantTools](https://3druck.com/programme/slant3d-startet-slanttools-browser-generatoren-erzeugen-druckfertige-3d-modelle-ohne-cad-kenntnisse-53164087/) (Slant3D) | Generatoren: Box, Platinengehäuse, Zahnrad, Gridfinity, Vase, Schriftzug | n. g. | Browser |
| 01.07., 26.06. | [ParamaCraft lite](https://3druck.com/programme/paramacraft-lite-parametrischer-modell-editor-jetzt-kostenlos-ueber-bambu-labs-makerworld-verfuegbar-21159558/), [Bento-Generator](https://3druck.com/programme/ohne-cad-zum-passenden-tray-bento-generator-auf-bambu-labs-makerworld-38159282/) (MakerWorld, Bambu Lab) | Vorlagen per Regler anpassen, „ohne CAD“ | gratis | Browser am Katalog |
| 15.09. | [Additive App Suite](https://3druck.com/programme/trinckle-bringt-additive-app-suite-fuer-automatisierte-3d-druck-konstruktion-23162953/) (trinckle, Berlin) | Betriebsmittel aus Parametern (Bohrschablonen, Spannbacken) | n. g. | in GrabCAD Print |

### Teilen mit Verbindern

| Datum | Programm (Hersteller) | Überschneidung mit Solidon | Preis / Lizenz | Plattform |
|---|---|---|---|---|
| 07.10. | [ModelSplitter](https://3druck.com/programme/modelsplitter-kostenlose-browser-app-zerlegt-3d-modelle-in-druckbare-teile-mit-passstiften-07163699/) (Einzelentwickler) | Schnitt gerade oder gekrümmt, Planer senkt die Teilezahl (58 statt 112), Passstifte, **eingravierte Nummern und PDF-Montageanleitung**, Datei bleibt lokal | Beta gratis; Pro £25 statt £49 einmalig (H) | Browser |
| 16.10., 21.09. | [SnapSplit 0.2.0](https://3druck.com/programme/blender-add-on-snapsplit-0-2-0-teilt-3d-modelle-per-freihand-schnitt-und-setzt-verbinder-41164144/) (Betakontext) | Freihandschnitt, Verbinder samt Schwalbenschwanz, Prüfung der Nahtpaare | n. g. (Gumroad, Superhive, GitHub) | Blender-Add-on |
| 19.08. | [Bambu Studio 2.8](https://3druck.com/programme/bambu-studio-2-8-neue-funktion-erzeugt-montageanleitungen-automatisch-aus-cad-dateien-49162009/) (Bambu Lab) | Montageanleitung aus STEP als PDF, Markdown oder Video | gratis | Desktop |

### KI-Generierung mit Druckbezug

| Datum | Programm (Hersteller) | Überschneidung mit Solidon | Preis / Lizenz | Plattform |
|---|---|---|---|---|
| 12.08., 17.09., 16.10. | [Meshy 7](https://3druck.com/programme/meshy-7-neues-ki-modell-fuer-praezisere-3d-modelle-neue-werkzeuge-fuer-den-3d-druck-12161778/), [7.1](https://3druck.com/programme/meshy-7-1-ultra-4k-modus-erzeugt-ki-3d-modelle-mit-4096%c2%b3-aufloesung-und-feineren-oberflaechendetails-37163042/), [Meshy Edit](https://3druck.com/programme/meshy-edit-ki-werkzeug-aendert-einzelne-bereiche-von-3d-modellen-vor-dem-druck-35164084/) | **Auto Split** mit Anordnung auf der Platte, Multicolor 2.0 mit bis zu 16 Farben als 3MF, Druckbarkeitsprüfung und Sockel, Bereich per Satz ändern | Download ab Pro; laut [costbench, Aug. 2026](https://costbench.com/software/ai-3d-generation/meshy/) Pro 20 $/Monat; Edit 20 Credits | Web |
| 23.07. | [Meshy-Finanzierung](https://3druck.com/programme/meshy-erhaelt-400-millionen-dollar-fuer-ki-generierte-3d-modelle-25161099/) | 400 Mio. $ | – | – |
| 24.09., 31.08. | [Tripo P2.0](https://3druck.com/programme/tripo-p2-0-erzeugt-3d-modelle-mit-quad-topologie-und-gezielter-mesh-bearbeitung-53163246/) | Quad-Netze, Teile beim Erzeugen getrennt, Mesh Edit für markierte Bereiche | Pro rund 19,90 $/Monat, Quellen widersprüchlich ([costbench](https://www.costbench.com/software/ai-3d-generation/tripo-ai/)) | Web |
| 23.07., 07.06. | [Tripo-Finanzierung](https://3druck.com/programme/tripo-ai-150-millionen-us-dollar-fuer-3d-foundation-models-und-world-models-58161095/) | 150 Mio. $, im Juni knapp 200 Mio. $ | – | – |
| 31.07., 23.09. | [Hi3D V3.0](https://3druck.com/programme/hi3d-v3-0-soll-ki-generierte-3d-modelle-besser-fuer-den-druck-vorbereiten-30161346/), [Hi3D Agent](https://3druck.com/programme/hi3d-agent-verbindet-ki-gestuetzte-3d-erzeugung-mit-workflows-fuer-den-3d-druck-39163217/) (Math Magic) | Teilen mit Steckverbindern, Farbbereiche für Mehrfarbdrucker; ein Agent wählt die Werkzeuge | n. g. | Web |
| 24.07. | [Modly](https://3druck.com/programme/modly-open-source-app-erzeugt-3d-modelle-lokal-aus-bildern-per-ki-49161174/) (Lightning Pixel) | Bild→Netz **lokal** auf der eigenen Grafikkarte | MIT, gratis | Win, Linux, Mac (Apple Silicon) |
| 15.09. | [InstructMesh](https://3druck.com/programme/instructmesh-soll-ki-generierte-3d-modelle-druckbarer-und-funktionaler-machen-20162952/) (MIT CSAIL) | TRELLIS + GPT-4, Bereiche per Sprache ändern, Ziel Druckbarkeit | Forschung | – |
| 28.09., 05.09., 10.09., 09.06. | [Fünf-KI-Brückentest](https://3druck.com/programme/fuenf-kis-im-3d-druck-vergleich-chatgpt-claude-und-co-muessen-eine-tragfaehige-bruecke-bauen-38163368/), GPT-6 Astra, CAD Arena, Claude Fable 5 | Allgemeine Sprachmodelle bauen druckbare Teile direkt; Claude Opus 5.5 gewann den Brückentest | – | – |

### Druckanalyse, Slicer, Übergabe

| Datum | Programm (Hersteller) | Überschneidung mit Solidon | Preis / Lizenz | Plattform |
|---|---|---|---|---|
| 16.10. | [OrcaSlicer 2.5.0 Alpha](https://3druck.com/programme/orcaslicer-2-5-0-alpha-python-plugins-farbmischung-und-unterstuetzung-fuer-bandrucker-21164141/) | **experimenteller Design-Tab für parametrische Teile**, Texture Displacement, Python-Plugins ([GitHub-Release](https://github.com/OrcaSlicer/OrcaSlicer/releases)) | AGPL, gratis | Win, Mac, Linux |
| 01.09., 07.09. | [PrusaSlicer 3.0 Preview](https://3druck.com/programme/3d-drucker-hersteller-prusa-veroeffentlicht-prusaslicer-3-0-als-preview-19162372/), [Android/Browser-Prototyp](https://3druck.com/programme/prusaslicer-auf-android-und-im-browser-josef-prusa-zeigt-interne-prototypen-12162693/) | neue Oberfläche, Lua-Plugins, mehrere Projekte | AGPLv3 | Desktop, Prototyp mobil |
| 29.07. | [Prusa EasyPrint](https://3druck.com/programme/prusa-abo-modell-fuer-den-cloud-slicer-easyprint-sorgt-fuer-kritik-firmengruender-reagiert-51161274/) | Cloud-Slicer im **Abo** (8,99 und 29,99 $/Monat), Kritik der Gemeinschaft | Abo | Browser |
| 25.09. | [Printfins](https://3druck.com/programme/printfins-browser-tool-ersetzt-baumstuetzen-durch-stuetzrippen-im-stl-modell-und-spart-filament-20163317/) (Einzelentwickler) | Stützrippen ins STL, Ausrichtungsvorschlag | gratis, Quelltext auf GitHub | Browser |
| 16.10. | [InsertPlan](https://3druck.com/programme/insertplan-kostenloses-browser-tool-berechnet-druckpausen-fuer-magnete-muttern-und-lager-22164116/) | Druckpausen für Magnete und Muttern, prüft das Spiel | gratis | Browser |
| 29.09. | [BumpMesh](https://3druck.com/programme/bumpmesh-texturgalerie-waechst-um-64-oberflaechenmuster-fuer-3d-druckmodelle-39163431/) (CNC Kitchen) | Texturen aus Graustufenbild, 64 neue Muster | gratis, Quelltext offen | Browser, lokal |
| 10.06. | [Bambu Handy 3.22](https://3druck.com/programme/bambu-handy-3-22-0-neue-oberflaeche-und-automatische-filamentverwaltung-17158346/) | Filamentverwaltung gleicht das verwendete Filament mit dem Bestand ab | gratis | Mobil |
| 28.07., 22.09. | [FreeCAD-MCP](https://3druck.com/programme/freecad-mit-claude-oder-chatgpt-mcp-schnittstelle-erlaubt-ki-gesteuerte-cad-modelle-14161271/), [Hermes-Skill](https://3druck.com/programme/ki-agent-fuer-den-3d-druck-entwickler-veroeffentlicht-skill-unter-offener-lizenz-34163161/) | Agent steuert CAD bzw. slict mit Orca und lädt hoch | offen (MIT beim Skill) | – |

**Was das Feld seit Juni bewegt hat:**

1. **Fast alles Neue ist gratis, läuft im Browser und braucht kein Konto**
   (OwlCAD, layerling, SolidCraft, ModelSplitter, Printfins, BumpMesh,
   MakerLab).
2. **Solidons Teilfunktionen gibt es jetzt einzeln.** STL zu CAD bieten
   ShapeAnywhere, stl2step und Backflip, das Teilen mit Stiften ModelSplitter,
   SnapSplit, Meshy und Hi3D. Druckprüfung vor dem Slicen haben OwlCAD, Creallo
   und Meshy, Texturen BumpMesh und Orca 2.5, einen MCP-Server OwlCAD,
   SolidCraft, layerling und FreeCAD.
3. **Die KI-Generatoren holen die Druckvorbereitung zu sich** (Meshy Auto
   Split, Multicolor und Edit; Hi3D; Tripo) und haben dafür das Kapital
   (Meshy 400 Mio. $, Tripo 150 Mio. $).
4. **Der nächste Verwandte ist deutsch:** Constructor AI wirbt „ohne
   CAD-Kenntnisse“, verkauft einmalig für 139 € und läuft nach der Aktivierung
   offline, allerdings nur unter Windows.

---

## (B) Funktionsvergleich mit Solidon

### B1 Wo Solidon allein steht (in den 40 Funden)

1. **Die ganze Kette in einem Programm, lokal.** Solidon erkennt Merkmale in
   der fremden STL und ändert sie im Verlauf, nimmt die Passung aus dem
   Materialprofil, prüft mit Schichtanalyse, übergibt mit Einstellungen an
   acht Slicer und liest den G-Code zurück (README, „Zusätzliche Programme“).
   Kein Fund deckt mehr als zwei dieser Glieder ab. Der Nachbau bei
   ShapeAnywhere ist eine bezahlte Browser-Beta, Backflip rechnet in der Cloud
   und gibt an Fusion aus, und stl2step wandelt um, ohne zu bearbeiten.
2. **Passung aus dem kalibrierten Materialprofil.** Das hat kein Fund. Bei
   PrusaSlicer müssen Dübel laut Prusa-Forum (2023) von Hand auf Toleranz
   gebracht werden ([Prusa-Hilfe](https://help.prusa3d.com/article/cut-tool_1779),
   [Forum](https://forum.prusa3d.com/forum/prusaslicer/prusa-2-6-0-alpha4-cut-tool)).
   Solidons automatisches Teilen nimmt das Spiel der Stifte aus dem
   Materialprofil (README, „Auto Split“).
3. **Druckrat mit Begründung für jeden Slicer.** Das hat kein Fund. Slicer
   raten nur für sich selbst, der Hermes-Skill nur für Orca und einen Drucker.
4. **Einmalkauf, offline nach der Freischaltung, drei Plattformen, sechs
   Sprachen.** Einmalkauf und Offline teilen nur Constructor AI (139 €, nur
   Windows, Deutsch) und Plasticity (175 $). Solidon ist mit 69 € günstiger
   und läuft auf drei Plattformen.

**Nicht mehr allein**, und deshalb kein Aufmacher mehr: „ohne CAD“
(Constructor, SlantTools, MakerLab), „Druckprüfung vor dem Slicen“ (OwlCAD,
Creallo, Meshy) und „Teilen mit Passstiften“ (ModelSplitter, Meshy, Hi3D,
SnapSplit, Schnittwerkzeuge von Prusa und Bambu). Auch „KI-Agent mit Undo und
MCP“ gehört dazu: OwlCAD wirbt mit einem KI-Modus, der sich zurücknehmen lässt,
und hat 29 MCP-Werkzeuge.

### B2 Lücken, nach Wichtigkeit für einen Käufer

| # | Lücke | Wer es hat (Quelle, Datum) | Solidon heute |
|---|---|---|---|
| 1 | **Ohne Hürde ausprobieren** | OwlCAD, layerling, SolidCraft, ShapeAnywhere: Browser ohne Konto; Plasticity 30 Tage Test; Constructor online ab 4,99 €/24 h (Herstellerseiten, 17.10.) | Download von 170 bis 254 MB. **Ab 1.0 zunächst keine Testphase** (README, „Die öffentliche Demo“: `TRIAL_FROM` = None), ab dem 01.12. also Kauf ohne Probe |
| 2 | **KI ohne Einrichtung** | OwlCAD Pro, Meshy, CADlingo, Constructor: KI ist enthalten, gegen Credits oder Abo | Chat nur mit eigenem API-Schlüssel oder mit Ollama ab 8 bis 16 GB Grafikspeicher; Weg 3 braucht ComfyUI und 10 bis 18 GB Platz (Startseite, Systemvoraussetzungen) |
| 3 | **Läuft auf einem normalen Laptop** | Constructor AI: 1280 × 720 (Herstellerseite, 17.10.) | Verlangt 1920 × 1080 bei 100 %; viele Laptops stehen ab Werk auf 125 oder 150 % (Startseite, Systemvoraussetzungen) |
| 4 | **Zahnrad- und Gridfinity-Generator** | OwlCAD, SlantTools, layerling, SolidCraft; Gridfinity auch in der [3Druck-Übersicht vom 02.09.](https://3druck.com/programme/kostenlose-tools-3d-druck-uebersicht-44162321/) | Fehlen unter den 50 Bausteinen (Grep über `app/core/knowledge/parts/`, 17.10.) |
| 5 | **Teilenummern und Montageplan beim Teilen** | ModelSplitter (07.10.), Bambu Studio 2.8 (19.08.) | Dateinamen wie `teil_3von7` und eine Explosionsansicht; in `autosplit.py` keine eingeprägte Nummer gefunden (Grep, 17.10.; Vermutung, dass es keine gibt) |
| 6 | KI-Änderung an einem Bereich per Satz | Meshy Edit (16.10.), Tripo P2.0 (24.09.), InstructMesh (15.09.) | Pinsel und Netzwerkzeuge, keine Änderung per Satz; geringer Rang, weil Solidons Rolle hinter dem Generator liegt |
| 7 | Mehr Farben aus der Textur | Meshy bis 16 Farben (12.08.); Bambu Studio 2.7 Textur→Farbe (15.05.) | Bis zu acht Filamente je Objekt (README, „Farbe und Filamente“) |
| 8 | Mobil oder Tablet | Forma3D (15.09.), PrusaSlicer-Prototyp (07.09.) | Nur Desktop, bewusst |
| 9 | Baugruppen und Gelenke | SolidCraft, OwlCAD | Bewusst ausgeschlossen, die Website sagt es |

### B3 Solidon kann es, zeigt es aber nicht vorn

- **„STL wieder bearbeitbar“** ist der Titel der Konkurrenz (ShapeAnywhere
  11.10., stl2step 13.10., Backflip). Solidon kann es mit *Modell nachbauen*,
  *In Flächen und Kanten umwandeln* und dem STEP-Export (README, „Exakte
  Körper“). Auf der Startseite steht das nur in der Zeitleiste unter 0.5.2.
  Die Funktionsseite führt das Umwandeln als Werkzeugkarte, das Wort
  „nachbauen“ kommt dort nicht vor (Grep, 17.10.).
- **Druckkosten je Teil aus dem Spulenpreis**
  (`app/core/filament_usage.py: costs_for`). OwlCAD und Creallo werben genau
  damit, auf Solidons Startseite fehlt es.
- **Schwalbenschwanz-Dübel**: Den Stift gibt es als Profil `dovetail`
  (`parts/mechanics.py`), SnapSplit wirbt damit am 21.09. als Neuheit.

---

## (C) Website-Muster der Besten und ihre Wirkung

Abgerufen am 17.10.2026. Das baut auf M1 bis M12 der Durchsicht vom 30.08.
auf (`konzepte/archiv/durchsicht-website-2026-08.md`). Wiederholt ist nur, was
neue Belege hat.

| # | Muster | Wer, wie | Warum es wirkt |
|---|---|---|---|
| C1 | **Ein Knopf, das System erkannt** | [Plasticity](https://www.plasticity.xyz/): „Download for Windows“ neben „Try for free“; [SolidCraft](https://solidcraft.io/): „Download for Windows“ neben „Try in your browser“ | Keine Wahl zwischen Ziel und Download; ein Klick weniger als jede Auswahlliste |
| C2 | **Sofort spielen, bevor man lädt** | [OwlCAD](https://owlcad.com/) „Start without an account“, [ModelSplitter](https://modelsplitter.com/) „Play with the demo egg“, ShapeAnywhere „Als Gast testen“ | Wer selbst einen Regler zieht, will das Programm, bevor er nach dem Preis fragt |
| C3 | **Das Kaufmodell steht in der Überschrift** | Plasticity H1 „… no subscription“, Einmalkauf 175 $ bzw. 299 $; [Constructor](https://constructorai.eu/) setzt „Einmal kaufen“ als Häkchen unter den Knopf | Nimmt die größte Kaufangst zuerst. Die Kritik am EasyPrint-Abo (29.07.) zeigt, wie empfindlich die Szene ist |
| C4 | **Der Ablauf als nummerierte Schritte im Aufmacher** | Constructor: Beschreiben → Konstruieren → Prüfen → STL und G-Code; SolidCraft: 01 Sketch bis 04 Exchange | Zeigt in fünf Sekunden, was man tut, statt was das Programm ist |
| C5 | **Anwendungsfälle als Reiter über einer Bühne** | Meshy: Schnelle Generierung / 3D-Druck / Spiele & Medien; Plasticity: Direct editing / Dimensioning / Surfacing / Materials / Export | Jeder Besucher findet seinen Fall, und die Seite bleibt kurz |
| C6 | **Kurze Filme der Handlung, ohne Playerleiste** | SolidCraft: drei Filme, darunter „Höhe von 24 auf 32 mm“; Plasticity: Bühne unter den Reitern | Man sieht die Änderung geschehen. Eine Playerleiste macht daraus ein Video statt eines Produkts |
| C7 | **Fremde Zahl, Bewertung, Partner** | [Meshy](https://www.meshy.ai/): 12 Mio.+ Nutzer, G2 und Trustpilot 4,8, Logos von Bambu Lab, Elegoo und Flashforge; [Tinkercad](https://www.tinkercad.com/): 100 Mio. Menschen, 800 Mio. Entwürfe; [Creallo](https://atlas.creallo.com/en/): 10 000+ Projekte, 4,9; [Shapr3D](https://www.shapr3d.com/): G2 4,8 aus 173 Bewertungen | Kaufentscheidungen sind sozial; eine fremde Zahl wiegt mehr als jede eigene |
| C8 | **Ein Foto des echten Drucks** | Constructor: Foto einer gedruckten Eule, „Echtes Praxisbeispiel“; Meshy und Creallo: kaputtes und repariertes Netz nebeneinander | Der Kunde kauft das Teil in der Hand, nicht das Bild im Programm |
| C9 | **Vergleichsseiten gegen Bekanntes** | OwlCAD: eigene Seiten gegen Tinkercad, Onshape, Fusion 360; layerling: Tinkercad-Vergleich | Holt Suchanfragen wie „Alternative zu …“ ab und beantwortet die Frage, mit der der Käufer kommt |
| C10 | **Datenschutz als prüfbarer Satz** | ModelSplitter: „Modell verlässt den Browser nicht“ und eine Liste dessen, was gezählt wird; Constructor: „Diese Website setzt keine Cookies“ | Glaubwürdig, weil prüfbar; ein Versprechen ohne prüfbaren Satz wirkt daneben schwächer |
| C11 | **Versionszeile direkt am Knopf** | SolidCraft: „v0.14.0 available · Windows / macOS / Linux / FreeBSD“ | Zeigt, dass das Projekt lebt, und nennt die Plattform, bevor jemand fragt |
| C12 | **Schlanke Startseite, Tiefe auf Unterseiten** | OwlCAD: ein Abschnitt je Fähigkeit, Tiefe auf eigenen Seiten; Meshy: acht Abschnitte | Wer überzeugt ist, klickt weiter. Wer zweifelt, scrollt nicht 30 Bildschirme |
| C13 | **Kurze Lernfilme** | [SindriCAD](https://tinkeratlas.com/sindricad): elf Clips, meist unter einer Minute | Senkt die Angst vor dem ersten Start |
| C14 | **Hinweis auf die offizielle Quelle** | [OrcaSlicer](https://www.orcaslicer.com/) nennt die offiziellen Domains und warnt vor gefälschten Installern | Wird wichtig, sobald ein bezahltes Programm Fälschungen anzieht (ab 01.12.) |

---

## (D) Befunde zur heutigen solidon3d.de

Gemessen am 17.10.2026 auf der Live-Seite. Bei 390 px: 1 294 KB übertragen,
11 Anfragen, größte sichtbare Fläche nach 1,3 s, Seitenlänge **27 168 px**.
Bei 800 px: 18 767 px. Die Ladezeit ist stark und bleibt; die übrigen Befunde
stehen nach Gewicht geordnet.

| # | Abschnitt | Ist (wörtlich bzw. gemessen) | Gegen Muster | Befund |
|---|---|---|---|---|
| D1 | Preis, Kaufweg ab 01.12. | „Nur die Demokarte hat einen Knopf; gekauft wird vor dem 1. Dezember nichts“ (`website/CLAUDE.md`). Ab 1.0 zunächst keine Testphase (README) | C2, C3 | Ab dem 01.12. gibt es keinen kostenlosen Einstieg mehr, während jeder Wettbewerber gratis startet. **Größtes Risiko für den Verkauf** |
| D2 | Aufmacher, Knopf | „Jetzt kostenlos herunterladen“ springt nach `#download`. Dort öffnen Linux und macOS einen Auswahldialog, also drei Klicks bis zum Mac-Paket | C1 | Kein erkanntes System, kein direkter Download |
| D3 | Ziele der Knöpfe | Kopf „Demo“ → `#download`; Schluss „Zur Demo“ → `/#demo` (Preis); Funktionsseite „Demo“ → `/#preis` | C1, M7 | Drei Ziele für dieselbe Handlung; WB6 vom 30.08. ist noch offen |
| D4 | Aufmacher, Kicker | „3D-Modelle bearbeiten & erstellen — ohne CAD-Vorkenntnisse“ | – | Fast wortgleich mit Constructor („3D-Konstruktion ohne CAD-Kenntnisse“); SlantTools und MakerLab sagen dasselbe. Das unterscheidet nicht mehr |
| D5 | Aufmacher, Lead | „… prüft das Teil vor dem Slicen auf Druckrisiken und gibt es an deinen Slicer weiter“ | B1 | Die zwei Dinge, die nur Solidon kann, fehlen: die Passung aus dem eigenen Filament und Einstellungen mit Begründung für jeden Slicer |
| D6 | Aufmacher, Film | Das volle 2560-px-Fenster ist auf rund 720 px verkleinert, die Oberfläche unlesbar; darüber die Playerleiste „0:11 / 0:12“ (Bildschirmfoto 1440 px) | C6 | Wirkt wie ein eingebettetes Video. Die Bohrung ist klein, die Handlung schwer zu sehen. Ein Zuschnitt aus der Vollbildaufnahme ist nach `website/CLAUDE.md` erlaubt |
| D7 | Mobil, erster Bildschirm | Die Kopfzeile ist zweizeilig, sechs Häkchen stehen auf vier Zeilen, das Produktbild beginnt erst bei 692 px (bei 390 × 844) | C12 | Der erste Bildschirm zeigt kein Produkt |
| D8 | Länge und Gewichtung | 27 168 px mobil, also rund 32 Bildschirmhöhen. Bei 800 px ist *Unterstützen* mit 2 654 px höher als *Preis und Lizenz* mit 1 730 px, *Vier Wege* hat 3 043 px | C12 | Die Seite verkauft Spenden ausführlicher als das Produkt |
| D9 | Kennzahlenband | „190 Operationen“, „50 geprüfte Bausteine“, „243 Normteilmaße“, „20 Druckerprofile“, „12 Beispielprojekte“, „0 Konten“ | C7 | Nur eigene Zählungen, keine Nutzer, keine Stimme, keine Presse. 3Druck.com hat zweimal berichtet und steht nirgends (WB3 vom 30.08. offen) |
| D10 | „Was am Ende auf dem Bett liegt“ | Die Überschrift verspricht das Bett; `galerie-gehaeuse.webp` zeigt eine graue Box in der Ansicht des Programms | C8 | Keine Fotos gedruckter Teile, obwohl Robert selbst druckt (WB4 offen) |
| D11 | Vier Wege, Weg 3 | „Die vollständige Lizenz- und Herkunftskette der Gewichte von TRELLIS.2, FLUX.2 [klein] und dem Freisteller BiRefNet wird noch geprüft.“ | – | Interner Prüfvermerk in einem Verkaufsabschnitt; er gehört auf `ki-modelle.html` |
| D12 | Unterschied, erste Karte | „39 Referenzanfragen“ als große Zahl | C7 | Eine Zahl ohne Ergebnis. Ein Käufer versteht sie nicht, und die gemessenen Quoten lokaler Modelle stehen nur im README (21 und 22 von 39) |
| D13 | STL zu CAD | *Modell nachbauen* erscheint nur in der Zeitleiste (0.5.2) | B3 | Genau das Thema der Konkurrenz liegt versteckt |
| D14 | Systemvoraussetzungen | „Mindestens 1920 × 1080 Pixel bei 100 % … Viele Laptops … müssen dafür auf 100 % gestellt werden“ | – | Schreckt Laptop-Käufer vor dem Download ab; Constructor nennt 1280 × 720 |
| D15 | Ehrlich, Preis | „Kein Team.“, „Support nach Möglichkeit, ohne zugesagte Frist“, daneben PayPal und GoFundMe | C3 | Ehrlich und gut für die Demo. Neben einem Kaufangebot über 69 € signalisiert das Zerbrechlichkeit |

**Was stark ist und bleibt:** Die H1 „Aus STL wird das Teil, das du
brauchst.“ ist konkreter als bei jedem Wettbewerber. Ebenso stark sind die
Kaufzeile am Knopf („einmal kaufen, privat ab 69 €, ohne Abo“), die
nummerierten Schritte am Film, *Kennst du das?*, *Was Solidon3D nicht ist*,
der Sprachhinweis (OwlCAD macht es genauso), die FAQ mit Schema, die drei
Preiskarten und die Ladezeit.

---

## (E) Zehn Empfehlungen für die Website, nach Wirkung

1. **Den Kauf ab dem 01.12. mit einer Probe absichern** (D1). Möglich sind
   eine Testphase in 1.0 (der Code dafür ist gepflegt, README), eine
   Geld-zurück-Zusage oder eine dauerhaft freie Stufe, etwa Öffnen, Prüfen und
   Exportieren. Auf der Seite steht dann neben „Kaufen“ immer „Erst testen“.
   *Entscheidung Robert, weil es um Geld geht.*
2. **Ein Knopf, der direkt lädt** (D2, D3; C1): das System erkennen, etwa
   „Für Windows laden — 170 MB“, und darunter klein „Andere Systeme“. Jeder
   Download- und Demo-Knopf der Seite führt auf dieses eine Ziel.
3. **Ein Band mit fremden Belegen direkt unter dem Aufmacher** (D9; C7). Es
   zeigt „Berichtet auf 3Druck.com“ mit beiden Artikeln (als Text; ein Logo nur
   mit Recht), die Downloadzahl aus `count.php` und die ersten Stimmen aus
   Rückmeldungen, mit Einwilligung.
4. **Fotos echter Drucke** (D10; C8): die vier Galerieteile auf dem Centauri
   Carbon 2 drucken und fotografieren. Dazu ein Vorher-Nachher-Paar für Weg 1:
   die heruntergeladene STL, in die die Schraube nicht passt, und das
   gedruckte Teil, in dem sie steckt.
5. **Den Film im Aufmacher als Ausschnitt ohne Playerleiste zeigen** (D6, D7;
   C6). Er wird auf Bohrung und Maßfeld zugeschnitten, Steuerung erst beim
   Darüberfahren oder Antippen. Am Handy steht das Bild vor den Häkchen, die
   sechs Häkchen werden zu einer Zeile.
6. **Die Alleinstellung in den Aufmacher setzen** (D4, D5; B1). Der Kicker
   „ohne CAD-Vorkenntnisse“ weicht der Kette „Anpassen, Passung aus deinem
   Filament, prüfen, an deinen Slicer übergeben“. Darunter stehen drei
   Belegkarten: Passung nach Materialwechsel (Beispiel
   `passung-nach-materialwechsel.p3d`), Druckrat mit Begründung je Wert und
   Bohrung ändern.
7. **„STL wieder bearbeitbar“ als eigenen Abschnitt und eigene Seite** (D13;
   B3). Dazu gehören Merkmale erkennen, *Modell nachbauen* und der
   STEP-Export, mit Vorher und Nachher (Netz → Verlaufsschritte). Das zielt
   auf Suchen wie „STL bearbeiten“ und „STL in STEP umwandeln“, auf das Thema
   also, mit dem ShapeAnywhere, stl2step und Backflip gerade in der Presse
   stehen.
8. **Vergleichsseiten** (C9): Solidon gegen Meshmixer, Fusion Personal,
   Tinkercad und das Schnittwerkzeug der Slicer, sachlich und mit Quelle je
   Aussage. Vor einem namentlichen Vergleich mit einem Wettbewerber
   `/legal-review` (vergleichende Werbung).
9. **Die Startseite auf ein Drittel kürzen** (D8, D11, D15; C12).
   *Unterstützen* zieht spätestens zu 1.0 auf eine eigene Seite, auf der
   Startseite bleibt eine Zeile. Systemvoraussetzungen und lange FAQ-Antworten
   kommen als Anriss mit Verweis, der Prüfvermerk zu Weg 3 wandert auf
   `ki-modelle.html`. Mein Zielwert: unter 12 000 px bei 390 px.
10. **Das Kennzahlenband auf Kundennutzen umstellen** (D9, D12; WB11). Etwa:
    „12 s: Bohrung ändern statt neu konstruieren“ (die Länge des Films), „8
    Slicer“, „6 Sprachen“, „0 Konten“. Jede Zahl verweist auf ihren Beleg, die
    Karte „39 Referenzanfragen“ nennt ihr Ergebnis oder fällt weg.

## (F) Fünf Empfehlungen für die App bis 1.0

Rahmen: Laut Startseite kommen „große neue Funktionen … vor 1.0 nicht mehr
dazu“ (Entscheidung Robert). Die Punkte 1, 2 und 5 passen in diesen Rahmen,
für 3 und 4 braucht es Roberts Ja.

1. **Auf einem normalen Laptop vollständig bedienbar** (B2 Nr. 3, D14):
   Gemeint sind 1920 × 1080 bei 125 %, also 1536 × 864 logische Pixel, ohne
   abgeschnittene Bedienelemente. Danach wird die Systemvoraussetzung
   gesenkt. Das ist Fehlerbehebung, und es öffnet die größte Käufergruppe.
   (Wie verbreitet 125 % ab Werk ist, ist eine Vermutung; die Startseite sagt
   es selbst.)
2. **Testphase in 1.0** (B2 Nr. 1, E1): Der 14-Tage-Pfad ist gepflegt, es
   fehlt der gesetzte `TRIAL_FROM` im Verkaufsbau. *Entscheidung Robert.*
3. **Bausteine für Zahnrad und Gridfinity** (B2 Nr. 4). Sie sind die
   meistgebotenen Generatoren im Feld (OwlCAD, SlantTools, layerling,
   SolidCraft, MakerLab). Als Bausteine bleiben sie klein und tragen den
   vorhandenen Bereichsnachweis.
4. **Beim automatischen Teilen Nummern einprägen und einen Montageplan
   ausgeben** (B2 Nr. 5), wie ModelSplitter (07.10.) und Bambu Studio 2.8
   (19.08.). Das erweitert eine vorhandene Operation.
5. **Erkennung und Nachbau am Downloadkorpus messen und die Quote
   veröffentlichen** (B1 Nr. 1, B3). Gemeint ist der Anteil echter
   MakerWorld- und Printables-Modelle, deren Bohrungen erkannt und änderbar
   sind und deren Nachbau gelingt. Genau dort tritt die Konkurrenz an
   (ShapeAnywhere, stl2step, Backflip), und eine gemessene Zahl schlägt deren
   Versprechen. Das ist Qualitätsarbeit im Rahmen „Fehlerbehebung und
   Stabilität“.

**Bewusst nicht empfohlen:** Browser-App, Druckdienst, Abo und eigener Slicer
stehen unter „Was NICHT gebaut wird“ in `AGENTS.md`. KI ohne Einrichtung
(B2 Nr. 2) bräuchte ein gehostetes Backend mit laufenden Kosten; das ist eine
Entscheidung nach 1.0.

---

**Nicht belegt bzw. offen:** Preise von ShapeAnywhere (Mesh→CAD), SnapSplit,
Backflip, Hi3D und SlantTools; der aktuelle Stand von MakerWorld, Bambu Studio
und Tripo auf deren eigenen Seiten (Abruf gesperrt); Lizenz und Preis von
Forma3D. Die Tripo-Preise widersprechen sich in den Sekundärquellen.
