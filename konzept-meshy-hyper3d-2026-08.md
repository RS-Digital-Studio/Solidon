# Konzept — Solidon3D gegen Meshy und Hyper3D Rodin (12.08.2026)

Anlass ist eine Frage in vier Teilen: *Wie stehen Oberfläche, Funktionen,
Handbuch und Schnittstelle gegen die beiden führenden KI-3D-Generatoren?
Können wir mithalten?*

Die kurze Antwort steht am Anfang, weil sie die Reihenfolge alles Weiteren
bestimmt: **In zwei von fünf Bereichen sind wir deutlich überlegen, in einem
gleichauf, in zweien chancenlos — und der wichtigste Befund ist keiner dieser
fünf, sondern dass Meshy seit vier Wochen in unserem Feld steht.**

**Verhältnis zu den bestehenden Konzepten.** `konzept-wettbewerb-2026-08.md`
(11.08.) zieht das Feld in sechs Gruppen auf und behandelt die KI-Generatoren
als Gruppe G6 — in einer Tabellenzeile und in Abschnitt 2.4. Dieses Dokument
vertieft die zwei Vertreter, die der Auftrag nennt, und korrigiert **eine
Aussage von gestern**: Die Abgrenzung „unsere Rolle beginnt hinter deren
Ausgabe" (§42) stimmt weiter als Absicht, beschreibt den Markt aber nicht mehr.
Meshy hat die Ausgabe verlassen und ist in die Aufbereitung eingerückt.
`konzept-bedienung.md` ist die Durchsicht der eigenen Oberfläche; die
Befunde dort werden hier **nicht** wiederholt (Doku-Doktrin, Regel 3), Teil 3
prüft nur, was der Vergleich *zusätzlich* zeigt.

**Methode.** Der eigene Stand ist aus dem laufenden Code ausgelesen, nicht
erinnert: Register über `load_operations()` (Memory-Fund: ohne den Aufruf
fehlen sechzehn), Handbuch über `manual.pages()`, Abbildungen über den
Katalog, Website aus der Datei. Der Marktstand kommt aus den Seiten selbst,
abgerufen am 12.08.2026 — Preisseiten, Dokumentation, `llms.txt`,
Produktseiten. Preise sind Anhaltspunkte, keine Zusagen. Wo ich etwas nicht
messen konnte, steht „nicht geprüft" statt einer Schätzung.

---

## Teil 1 — Was die beiden heute sind

### 1.1 Meshy

Ein KI-Generator, der Text und Bilder in Netze verwandelt — und, das ist neu,
ein vollständiger 3D-Druck-Arbeitsablauf drumherum.

| | |
|---|---|
| **Geschäftsmodell** | Abo mit Guthaben. Frei: 100 Guthaben/Monat, Ergebnis unter CC BY 4.0. Pro 20 $/M (1.000 Guthaben), Premium 40 $, Ultra 100 $, Studio 70 $ (+10 $ je Mitglied), Enterprise auf Anfrage. Ab Bezahlplan gehören die Ergebnisse dem Nutzer. |
| **Erzeugen** | Text→3D, Bild→3D, Mehrbild→3D, KI-Texturierung, PBR-Satz (Albedo/Normal/Metallic/Roughness), HD-Textur in 4K |
| **Nachbearbeiten** | Remesh, UV-Unwrap, Retexture, Low-Poly mit gesteuerter Polygonzahl, Auto-Rigging (humanoid und vierbeinig), Animation mit über 600 Bewegungsvorlagen, Scene Compose, KI-Video |
| **3D-Druck** | Druckbarkeitsprüfung, Auto-Reparatur, **Auto Split**, Mehrfarbdruck mit Filamentzuordnung, Übergabe an acht Slicer |
| **Kreativlabor** | Fertigteile auf Knopfdruck: Schlüsselanhänger, Kühlschrankmagnet, Figur, Vinylfigur, Klemmbaustein-Figur, Lampe, Tastenkappe |
| **Schnittstelle** | REST-API mit Playground, Authentifizierung, Webhooks, Ratenbegrenzung, Changelog, Aufbewahrungsfristen |
| **Ökosystem** | Erweiterungen für Bambu Studio, Creality Print, OrcaSlicer, Cura, **Elegoo Slicer**, Lychee, Snapmaker, Flash Studio, dazu Blender, Unity, Unreal, Godot, Maya, 3ds Max, Roblox. Veröffentlichen nach MakerWorld, Printables, Thingiverse. Druckservice mit Versand. |
| **Größe** | Eigene Angabe: 100 Mio. erzeugte Modelle, 12 Mio. Nutzer, 10 Mio. Besuche im Monat, G2 und Trustpilot je 4,8 |

Der Werbesatz auf der Startseite lautet sinngemäß, Meshy sei die einzige 3D-KI,
die fürs Drucken trainiert wurde — wasserdicht, mannigfaltig, beim ersten
Versuch bereit zum Slicen.

### 1.2 Hyper3D Rodin

Derselbe Kern, andere Zielgruppe: Rodin geht auf Produktionspipelines und
Unternehmen, nicht auf den Drucker.

| | |
|---|---|
| **Geschäftsmodell** | Frei 0 $ (Einzelkauf 1,50 $/Guthaben), Creator 30 $/M (~60 Modelle), Business 120 $/M (~416 Modelle, API mit 120–240 Anfragen/Minute, 4K-Texturen), Enterprise mit privater Installation und eigenem LoRA. Bildungstarif. |
| **Stärke** | Tempo und Auflösung: Gen-2.5 nennt ~4 s für die Geometrie, ~5 s für das ganze Modell, über 10 Mio. Polygone |
| **Kontrolle** | **3D ControlNet** — Erzeugung wird über Hüllquader, Voxel oder Punktwolke geführt. Iteratives Aufteilen in bearbeitbare Teile, partielle Bearbeitung ausgewählter Bereiche, Smart Low-Poly. |
| **Werkzeugkasten** | OmniCraft: HDRI-Erzeuger, Texturerzeuger, Bild- und Videoerzeuger, SVG→3D, Mesh-Editor, KI-Avatare |
| **Unternehmen** | SSO über SAML 2.0, Identity-Provider-Anbindung, domänenbasierter Zugang, Teams und Rollen, geteilte Asset-Arbeitsbereiche, Prüfprotokolle |
| **3D-Druck** | Nur als Anwendungsfall genannt, plus STL im Export. Keine Druckbarkeitsprüfung, keine Slicer-Anbindung, kein Mehrfarbdruck. |

### 1.3 Der Befund, aus dem alles andere folgt

Von den beiden ist **Hyper3D der ungefährlichere**. Rodin baut Assets für
Spiele, Film und Produktvisualisierung; der Drucker ist eine Fußnote. Wer dort
ein Teil erzeugt, das an eine vorhandene Kante passen soll, bekommt Polygone,
keine Maße.

**Meshy dagegen steht seit kurzem auf unserem Feld.** Vier ihrer Funktionen
heißen fast wörtlich wie unsere:

| Meshy | Solidon |
|---|---|
| Analyze Printability | Prüfbericht, Analysekarten |
| Repair Printability | Op `repair`, Reparaturkette |
| **Auto Split** | Ops `split_plane`, `split_pinned` — im Menü „Automatisch teilen" |
| Multi-Color Print | Farb-Ops, 3MF mit Materialschlitzen, `check_filament_changes` |
| 3D Agent im Chat | Agentenschicht, Chat |
| Übergabe an Elegoo Slicer | `export/handover.py`, `slicer_keys.py` |

Das ist kein Zufall und keine Kopie in eine Richtung — es ist derselbe
naheliegende Arbeitsablauf, den beide gefunden haben. Die Folge ist trotzdem
unangenehm: **Der Satz „wir fangen an, wo die Generatoren aufhören" ist als
Abgrenzung nicht mehr selbsterklärend.** Ein Kunde, der beide Seiten sieht,
liest zweimal dieselbe Versprechung. Der Unterschied ist real und groß (Teil 2),
aber er muss ab jetzt *gezeigt* werden, statt behauptet.

---

## Teil 2 — Funktionen, Bereich für Bereich

Fünf Bereiche, jeder mit Beleg. „Wir" ist der gemessene Stand vom 12.08.2026:
**77 Operationen in 15 Kategorien, 16 Bausteine in 7 Gruppen.**

### 2.1 Erzeugen aus Text und Bild — chancenlos, und das ist in Ordnung

| | Meshy | Rodin | Solidon |
|---|---|---|---|
| Text→Netz | ja, unter 1 min | ja, ~5 s | über ComfyUI, lokal, Hunyuan3D 2.1 |
| Bild→Netz | ja | ja, mit Multi-View | ja, dasselbe Backend |
| Steuerung der Form | Prompt | **Hüllquader, Voxel, Punktwolke** | Prompt |
| PBR-Texturen | 4K | 4K | nein |
| Voraussetzung | Konto und Guthaben | Konto und Guthaben | **eigene Grafikkarte, ComfyUI installiert** |

Gegen zwei Häuser mit Kapital und eigenen Modellen gewinnen wir diesen Punkt
nicht, und der Bauplan sagt das selbst (§42): generierte Netze sind maßlich
wertlos, unsere Rolle beginnt danach. Was daraus folgt, ist keine Aufholjagd,
sondern eine **Rollenklärung** — siehe Befund B3.

Bemerkenswert bleibt einer ihrer Punkte: Rodins ControlNet über Hüllquader
und Punktwolke ist der einzige Ansatz im Feld, der Erzeugung und Maß
zusammenbringt. Wer eine Box vorgibt, in die das Ergebnis passen muss,
bekommt ein Ergebnis, das hineinpasst. Das ist nahe an dem, was ein
Druckteil-Konstrukteur braucht.

### 2.2 Druckbarkeit prüfen — hier gewinnen wir deutlich

Das ist der wichtigste Abschnitt des ganzen Dokuments, weil er das einzige
Argument enthält, das man in einem Satz sagen kann.

**Was Meshys `analyze-printability` prüft** — aus ihrer eigenen Dokumentation:

- wasserdicht ja/nein
- Volumen
- nicht-mannigfaltige Kanten
- degenerierte Flächen
- Löcher (Randschleifen)

Und dann steht dort, ebenfalls in ihrer Dokumentation, der Satz, der die Sache
entscheidet: geprüft wird **nicht** auf Wandstärke, Überhänge, dünne Teile oder
Stützbedarf.

**Was wir prüfen** (Module und Funktionen aus dem Code):

| Prüfung | Stelle |
|---|---|
| Überhangwinkel je Schicht, schlimmster und gesamter | `slice/analysis.py` — `total_overhang`, `worst_overhang` |
| Inseln: Material ohne Verbindung nach unten | `island_layers` |
| schmalste Stelle im Querschnitt | `minimum_width`, `narrowest` |
| Brückenweiten | `_bridge_width` |
| Wandstärke gegen Extrusionsbahnen | Prüfbericht, Rasterbezug |
| Bauraum des echten Druckers | `geom/prepare.py` — `check_build_volume` |
| Kollisionen zwischen Objekten auf der Platte | `check_collisions` |
| Haftungsabstand | `export/writer.py` — `check_adhesion_clearance` |
| Filamentwechsel beim Mehrfarbdruck | `check_filament_changes` |
| Passungen gegen das Materialprofil | `scene/fits.py` |
| Gitterstrukturen auf Druckbarkeit | `geom/lattice.py` — `check_printable` |
| Texturmuster gegen Düsendurchmesser | `geom/texture_ops.py` |
| Orientierungssuche | `slice/orientation.py` |
| Druckeinstellungen aus der Geometrie ableiten | `slice/advise.py` |

Ihre Prüfung beantwortet: *Ist die Datei kaputt?* Unsere beantwortet: *Kommt
das Teil heil vom Bett und passt es dann?* Das sind zwei verschiedene Fragen,
und die zweite ist die, wegen der jemand druckt.

Dazu kommt eine Unterscheidung, die es dort gar nicht gibt: Regel 14 verlangt,
dass Kennzahlen aus Schichtanalyse und aus G-Code nie vermischt werden und die
Herkunft immer ausgewiesen wird. Meshy nennt eine Zahl und sagt nicht, woher.

### 2.3 Konstruieren — sie können es nicht, wir schon

Kein Vergleich möglich, weil auf der Gegenseite nichts steht. Meshy und Rodin
haben keinen Operationsstapel, keine Parameter, keine Ausdrücke, keine
Passungen, keine Normteile, keine Skizze, kein Undo über eine Transaktion.
Was sie „Bearbeiten" nennen, ist Neuerzeugen mit anderem Prompt.

Der Unterschied in einem Beispiel: Wer bei uns die Wandstärke von 2,4 auf 3,0
setzt, ändert einen benannten Parameter, und der Stapel rechnet neu — Bohrungen,
Deckel, Passungen ziehen mit. Wer das dort will, erzeugt ein neues Modell und
hofft.

Vier Punkte, die auf keiner Gegenseite ein Gegenstück haben:

- **Passungen** als eigene Beziehung zwischen Objekten, geprüft gegen das
  Materialprofil (Regel 7: keine Zahlenkonstante, Verweis auf `auto:<material>`)
- **Normteilmaße** aus einer Tabelle, nicht im Baustein eingetragen
- **Determinismus**: gleicher Startwert, gleiches Ergebnis, geprüft von der Suite
- **Ohne Netz, ohne Konto benutzbar** — bei beiden Gegenspielern undenkbar,
  das ganze Produkt ist der Dienst

### 2.4 Übergabe und Ökosystem — hier verlieren wir klar

| | Meshy | Solidon |
|---|---|---|
| Slicer-Erweiterungen | 8 | Übergabe über `handover.py`, keine Erweiterung im Slicer |
| Erweiterungen für 3D-Programme | Blender, Unity, Unreal, Godot, Maya, 3ds Max, Roblox | keine |
| Veröffentlichen | MakerWorld, Printables, Thingiverse direkt | keine |
| Druckservice | ja, mit Versand | nein (und soll auch nicht) |
| Formate Export | GLB, FBX, OBJ, USDZ, STL, 3MF, BLEND | STL, 3MF, OBJ, PLY, GLB, STEP |
| Formate Import | STL, OBJ, FBX, GLTF, GLB | STL, OBJ, PLY, OFF, GLB, GLTF, 3MF (`geom/mesh.py:31`) |

Zwei Dinge daran sind wichtiger, als sie aussehen:

**Erstens:** Der Import kann bereits GLB und GLTF — also genau das, was Meshy
und Rodin ausgeben. Die Kette *dort erzeugen, hier aufbereiten* ist technisch
offen. Ob dabei Farben und Materialzuordnung ankommen, ist **nicht geprüft**
und muss vor jeder Werbeaussage gemessen werden.

**Zweitens:** STEP im Export ist etwas, das keiner von beiden hat, und für den
Übergang in echtes CAD ist es das einzige Format, das zählt.

### 2.5 Fernsteuerung — zwei unvereinbare Modelle

| | Meshy/Rodin | Solidon |
|---|---|---|
| Art | REST über das Netz | MCP auf `127.0.0.1`, standardmäßig aus |
| Zweck | fremde Anwendung erzeugt Assets im Dienst | fremdes Programm bedient **diese Installation** |
| Authentifizierung | API-Schlüssel, Konto, Guthaben | keine — lokal, kein Netz |
| Grenzen | 20 Anfragen/s, 10–100 gleichzeitige Aufgaben je Tarif | keine |
| Kosten je Aufruf | 1–50 Guthaben | keine |
| Was hindurchgeht | alles, was der Dienst kann | genau die Operationen aus dem Register — **kein** OpenSCAD-Quelltext, **kein** Dateipfad |
| Rücknahme | Aufgabe löschen | Strg+Z, der Verlauf zeigt die fremde Herkunft |
| Dokumentiert | Playground, Endpunktreferenz, Webhooks, Changelog, Aufbewahrung | **eine Handbuchseite mit 980 Zeichen** |

Das Modell ist bei uns richtig gewählt und aus den harten Regeln abgeleitet
(11, 12, 13, 16). Die Dokumentation ist es nicht — siehe Befund B6.

---

## Teil 3 — Design und Oberfläche

Die Frage lautete, ob wir mithalten. Sie lässt sich nicht mit ja oder nein
beantworten, weil hier zwei verschiedene Dinge verglichen werden: eine
Webanwendung, die Ergebnisse ausstellt, und ein Werkzeugfenster, das Arbeit
ermöglicht.

### 3.1 Was ihre Oberflächen tun

Beide Startseiten und beide Anwendungen sind nach demselben Muster gebaut:

- **Das Ergebnis steht im Mittelpunkt.** Galerien mit Vorschaubildern, Likes,
  Namen der Ersteller. Rodin sortiert nach Charaktere, Sci-Fi, Fantasy,
  Möbel, Fahrzeuge; Meshy zeigt eine endlose Kachelwand.
- **Ein Eingabefeld, ein Knopf.** Die gesamte Bedienung des Kernwegs ist
  „beschreiben, drücken, warten".
- **Wartezeit wird zur Ware.** Rodin lässt die Rechenzeit wählen —
  Extreme-Low ~4 s bis Extreme-High ~80 s — und macht daraus ein
  Bedienelement statt eines Ärgernisses.
- **Sozialer Beweis überall.** Nutzerzahlen, Bewertungen, Zitate,
  Kundengeschichten.

### 3.2 Was unser Fenster tut

Gemessen am Handbuchbild `app/images/manual/de/main-window.png`: acht Menüs,
Werkzeugleiste mit fünf Einträgen, links Objektbaum mit Maßen, darunter
Parameter und Verlauf, rechts Prüfbericht und Chat mit Filterzeile, unten
sieben Viewportwerkzeuge, in der Statusleiste Gewicht und Druckdauer
(64 g · 4 h 21 min), oben rechts Drucker und Material.

Das ist eine **dichte, ehrliche Werkzeugoberfläche** — und für die Zielgruppe
richtiger als ein Eingabefeld. Drei Beobachtungen aus dem Vergleich, die die
eigene Durchsicht so nicht liefert:

**3.2.1 Wir zeigen Werkzeuge, sie zeigen Ergebnisse.** Im Objektbaum stehen
„Dose" und „Dose Deckel" als Text mit Maßen. Der Bausteinkatalog hat
gerenderte Vorschaubilder (Regel: wird gerendert, nicht gepflegt) — der
Objektbaum hat keine. Ein kleines Vorschaubild je Objekt wäre die billigste
Anleihe aus deren Gestaltung, die zu uns passt, weil sie nichts verspricht,
was nicht da ist.

**3.2.2 Das Modell ist grau.** Im Bild steht ein einfarbig graues Teil in
einem grauen Raum. Das ist für Geometrie korrekt und für den ersten Eindruck
teuer — jeder Vergleichsbildschirm, den ein Interessent nebeneinanderlegt,
zeigt links eine texturierte Figur und rechts einen grauen Kasten. Die
Analysekarten und die Schichtenvorschau *sind* unser farbiges Bild; sie
müssten im Marketingmaterial vorn stehen, nicht in Kapitel vier. (Regel 18
bleibt: keine Bedeutung allein über Farbe.)

**3.2.3 Wartezeit ist bei uns ein Problem, bei Rodin ein Regler.** Wir haben
zwei Qualitätsstufen über `ctx.quality` — im Fenster taucht diese Wahl nicht
als bewusstes Angebot auf, sondern als Einstellung. Rodins fünfstufiger
Aufwandsregler mit Sekundenangaben ist dieselbe Sache, nur als Versprechen
formuliert. Das ist übernehmbar, ohne dass sich an der Rechnung etwas ändert.

### 3.3 Was wir nicht übernehmen

Galerie, Likes, Community-Kachelwand, Kontozwang, endloses Scrollen. Das
verlangt einen Dienst, ein Konto und Serverbetrieb — alle drei stehen auf der
Liste dessen, was ausdrücklich nicht gebaut wird. Der Verzicht ist kein
Nachteil, der ausgeglichen werden muss; er ist die Zusage „kein Konto, kein
Abo", die auf der eigenen Preisseite steht.

---

## Teil 4 — Handbuch gegen `docs.meshy.ai`

Die Frage war, ob unser Handbuch alles so detailliert beschreibt. Beide Seiten
gemessen:

| | Meshy-Doku | Solidon-Handbuch |
|---|---|---|
| Aufbau | vier Pfade: Web App, API, Plugins, 3D Printing | 20 geschriebene Seiten + 15 aus dem Register erzeugte Referenzseiten |
| Umfang | nicht messbar (gehostet) | ~110.000 Zeichen, ~19.600 Wörter |
| Abbildungen | Quick Start **ohne Bilder** | 32 Verweise, 25 Abbildungen im Katalog, 6 Bildschirmfotos je Sprache |
| Sprachen | Englisch | Deutsch und Englisch, beide vollständig |
| Funktionsreferenz | von Hand gepflegt, ~20 Funktionen | **aus dem Register erzeugt, alle 77 Operationen mit Parametern, Grenzen und Einheiten** |
| Glossar | ja („3D-Glossar", eigene Seite) | ja („Wörterbuch", 3.330 Zeichen) |
| Fehlerbehebung | Tabelle je Seite | eine Seite „Wenn etwas nicht geht" (2.760 Zeichen) |
| FAQ | je Seite | nur auf der Website, nicht im Handbuch |
| Changelog | ja, für Webapp und API | **nein** |
| Best Practices fürs Prompting | eigene Seite | **nein** |
| Anwendungsfälle als Anleitung | Game Assets, 3D Printing | **nein** |
| Vergleichsführer | mehrere („Meshy vs. …") | **nein** |
| Suche | ja | ja, in `handbuch.html` |
| Lernmaterial daneben | Blog, Anleitungen, 3D-Druck-Akademie, Kundengeschichten, Hilfezentrum | keins |

**Das Urteil ist zweigeteilt.**

*Wo wir besser sind:* Die erzeugte Referenz ist ein struktureller Vorteil, den
sie nicht einholen können, ohne ihre Dokumentation genauso zu bauen. Bei uns
kann keine Operation undokumentiert existieren — Regel 4 verbietet den
Registereintrag ohne übersetzte Texte, und die Seite entsteht aus demselben
Eintrag. Ihre 20 Funktionsseiten sind Handarbeit und veralten einzeln. Dazu
kommen Bilder, wo ihr Quick Start keine hat, und zwei vollständige Sprachen.

*Wo wir schlechter sind:* Unsere geschriebenen Seiten sind **Fließtext**.
Zwischen 980 und 6.177 Zeichen, im Schnitt ~2.100 — gut geschrieben, aber ohne
die Formen, die beim Nachschlagen tragen: kein „Kurz gesagt" am Anfang, keine
nummerierten Abläufe, keine Fehlertabelle mit der wörtlichen Meldung in der
linken Spalte, keine Fragen. Wer im Programm eine Meldung liest und im Handbuch
danach sucht, findet den Wortlaut heute nicht.

Und vier Dinge fehlen ganz: Changelog, Anleitung zum Chat („wie sage ich es
dem Agenten"), aufgabenbezogene Anleitungen („eine Dose mit Deckel und
Dichtnut"), und eine Referenz der MCP-Werkzeuge.

---

## Teil 5 — Preis

| | Meshy | Rodin | Solidon |
|---|---|---|---|
| Einstieg | 0 $, Ergebnis unter CC BY 4.0 | 0 $, Vorschau vor Bestätigung | keine kostenlose Stufe (Demo) |
| Arbeitstarif | 20 $/M = 240 $/J | 30 $/M = 360 $/J | **49 € einmalig** (später 79 €) |
| Nach zwölf Monaten | 240 $ und nichts in der Hand | 360 $ und nichts in der Hand | 49 € und ein Programm, das läuft |
| Nach Kündigung | Konto weg, Modelle weg | Konto weg | läuft weiter |
| Rechnet an | Guthaben je Aufruf (1–50) | Guthaben je Modell | nichts |

Das ist unser zweitstärkstes Argument nach der Druckbarkeitsprüfung, und es
steht auf der Website (`#preis`) als Zahl — aber ohne die Rechnung daneben.
„49 € einmalig gegen 240 $ im Jahr" ist eine Aussage, die jeder versteht;
„49 € zur Einführung, später 79 €" ist eine Preisangabe.

Ein Punkt gegen uns, der ehrlich dazugehört: Beide haben eine kostenlose
Stufe, die dauerhaft benutzbar ist. Wer heute vergleicht, kann dort ohne
Risiko anfangen und muss bei uns zuerst zahlen oder die Demo nehmen. Die
Demo-Frist läuft laut Stand im Arbeitsbaum ab dem ersten Start.

---

## Teil 6 — Können wir mithalten?

Bereichsweise, ohne Beschönigung:

| Bereich | Urteil |
|---|---|
| **Druckbarkeit und Fertigungsurteil** | **deutlich überlegen** — sie prüfen fünf Topologiewerte, wir prüfen vierzehn Sachverhalte samt Fertigung |
| **Konstruieren mit Maß** | **konkurrenzlos** — auf der Gegenseite existiert nichts davon |
| **Handbuchtiefe zur eigenen Funktion** | **überlegen** (erzeugte Vollreferenz, Bilder, zwei Sprachen), **unterlegen** in Form und Auffindbarkeit |
| **Erzeugen aus Text und Bild** | **chancenlos** — und nach §42 auch nicht unser Rennen |
| **Reichweite, Ökosystem, Integrationen** | **chancenlos** — 12 Mio. Nutzer gegen einen Einzelentwickler |
| **Preis und Eigentum** | **überlegen**, wird aber nicht ausgespielt |
| **Erster optischer Eindruck** | **unterlegen** — grauer Kasten gegen texturierte Figur |

Der ehrliche Satz für die Website steckt in Zeile eins und zwei dieser Tabelle:
*Meshy erzeugt Dinge, die aussehen wie etwas. Solidon baut Teile, die passen.*

---

## Teil 7 — Befunde

Nummeriert, mit Priorität und Aufwandsschätzung. Was daraus beschlossen wird,
wandert nach `ROADMAP.md` — dieses Dokument beschließt nichts.

### B1 — Die Vergleichstabelle Druckbarkeit fehlt · **hoch** · klein

Ihre eigene Dokumentation sagt, dass Wandstärke, Überhänge, dünne Teile und
Stützbedarf nicht geprüft werden. Das ist ein Beleg, kein Werbespruch, und er
gehört auf die Website und in die Handbuchseite „Hinsehen, bevor gedruckt
wird" — als Tabelle, welche Frage welches Werkzeug beantwortet.

### B2 — Die Analysekarten müssen nach vorn · **hoch** · klein

Unser farbiges Bild sind Analysekarten und Schichtenvorschau, nicht das graue
Modell. Auf der Startseite steht heute keins davon prominent. Ein Bild, das
eine Überhangkarte neben dem fertig gedruckten Teil zeigt, sagt in einer
Sekunde, was drei Absätze nicht sagen.

### B3 — Die Rolle „bester Nachbearbeiter für generierte Netze" belegen · **hoch** · mittel

Der Import liest GLB und GLTF (`geom/mesh.py:31`) — die Kette Meshy→Solidon
ist offen. Was fehlt, ist der Beweis: ein durchgemessener Ablauf von einer
echten Meshy-Ausgabe bis zum druckfertigen Teil, mit Zahlen vorher/nachher.
**Vorher zu prüfen (offen):** Kommen Farbzuordnung und Materialschlitze beim
GLB-Import an? Ohne das ist die Kette bei Mehrfarbteilen unterbrochen.

### B4 — Handbuchform: Kurzfassung, Ablauf, Fehlertabelle · **mittel** · mittel

Je geschriebener Seite ein „Kurz gesagt" am Anfang und, wo es einen Ablauf
gibt, nummerierte Schritte. Wichtiger noch: eine Fehlertabelle, deren linke
Spalte die **wörtliche Meldung** aus dem Programm enthält. Die Meldungen
liegen bereits als übersetzte Texte vor; die Tabelle kann daraus erzeugt
werden statt gepflegt — dasselbe Muster wie die Op-Referenz.

### B5 — Vier fehlende Handbuchseiten · **mittel** · mittel

„Wie ich mit dem Chat spreche" (ihr Gegenstück: Prompting Best Practices),
zwei bis drei aufgabenbezogene Anleitungen vom Anfang bis zum Druck, ein
Changelog. Der Changelog existiert unter `Releases/` und muss nur ins Handbuch
gehoben werden.

### B6 — Referenz der MCP-Werkzeuge erzeugen · **mittel** · klein

Die Fernsteuerung hat 980 Zeichen Handbuch gegen ihre vollständige
Endpunktreferenz. Die Werkzeuge kommen aus `registry/surfaces.py`
(`tool_schemas`) — dieselbe Quelle, aus der die Op-Referenz entsteht. Eine
erzeugte Seite kostet wenig und schließt die auffälligste Lücke der
Dokumentation.

### B7 — Preisrechnung statt Preisangabe · **mittel** · klein

„49 € einmalig — Meshy Pro kostet 240 $ im Jahr, Rodin Creator 360 $" mit
Datum und Quelle. Dazu der Satz, der ihnen strukturell fehlt: nach der
Kündigung läuft hier alles weiter.

### B8 — Vorschaubilder im Objektbaum · **niedrig** · mittel

Die Renderstrecke für Bausteinvorschauen existiert. Sie auf Szenenobjekte
anzuwenden ist Fleißarbeit mit sichtbarer Wirkung — und die einzige Anleihe
aus deren Gestaltung, die nichts verspricht, was nicht da ist.

### B9 — Qualitätsstufe als Angebot statt als Einstellung · **niedrig** · klein

`ctx.quality` gibt es bereits. Rodin macht daraus einen Regler mit
Sekundenangaben. Bei uns könnte an der Stelle, wo eine lange Rechnung
beginnt, die Wahl mit einer Zeitschätzung stehen — Wartezeitverhalten nach
§2.8, nur als Angebot formuliert.

### B10 — Rodins ControlNet als offene Frage notieren · **offen** · groß

Erzeugung, die in einen vorgegebenen Hüllquader hineinrechnet, ist die einzige
Idee der Gegenseite, die unser Kernproblem berührt: generierte Netze haben
keine Maße. Ob unser ComfyUI-Weg so etwas kann, ist **nicht geprüft**. Das ist
keine Aufgabe, sondern eine Frage an den nächsten Konzeptdurchgang.

---

## Was ausdrücklich nicht folgt

Damit dieses Dokument nicht als Auftragsliste für einen Wettlauf gelesen wird,
den wir nicht führen:

- **Kein Wettlauf um Textur- und Mesh-Qualität.** Zwei Häuser mit eigenen
  Modellen und Kapital; unsere Rolle beginnt hinter ihrer Ausgabe (§42).
- **Kein Rigging, keine Animation, kein PBR, kein Videoerzeuger.** Nichts
  davon berührt ein gedrucktes Teil.
- **Keine Galerie, keine Community, kein Konto, kein Dienst.** Steht auf der
  Nicht-gebaut-Liste und ist Teil der Zusage.
- **Kein Kreativlabor mit Fertigteilen** in ihrer Form (Bild rein,
  Schlüsselanhänger raus). Unsere Entsprechung ist die Bausteinbibliothek —
  parametrisch, maßhaltig, ohne Konto. Sie darf wachsen, aber nicht zum
  Automaten werden.
- **Kein Druckservice.**

---

## Abnahme

Ein Durchgang gilt als erledigt, wenn:

1. B1 steht auf Website und Handbuchseite, mit Datum und Quellenangabe zur
   Gegenseite.
2. B3 ist gemessen: eine echte generierte Datei, der Ablauf bis zum Export
   dokumentiert, die Frage zu Farben beantwortet — ja oder nein, nicht
   „vermutlich".
3. B6 erzeugt seine Seite aus dem Register; ein Test hält fest, dass jedes
   Werkzeug der Fernsteuerung dort auftaucht.
4. Die Suite ist grün: `pytest`, `ruff check`, `ruff format --check`, `mypy`.

---

*Stand 12.08.2026. Der eigene Stand ist aus dem laufenden Code gemessen, der
Marktstand von den Seiten der Anbieter abgerufen. Preise und Nutzerzahlen sind
Angaben der Anbieter, keine geprüften Werte.*
