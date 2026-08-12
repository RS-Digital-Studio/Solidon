# Konzept — Solidon3D gegen Meshy und Hyper3D Rodin (12.08.2026)

Anlass ist eine Frage in vier Teilen: *Wie stehen Oberfläche, Funktionen,
Handbuch und Schnittstelle gegen die beiden führenden KI-3D-Generatoren?
Können wir mithalten?*

**Zweite, gründlichere Fassung.** Der erste Durchgang blieb an vier Stellen
bei Vermutungen stehen; sie sind jetzt gemessen, und zwei davon fielen anders
aus als angenommen. Was korrigiert wurde, steht in Teil 8 — nicht versteckt,
weil eine Korrektur mehr wert ist als eine Behauptung, die zufällig stimmte.

Die kurze Antwort: **In zwei von sechs Bereichen sind wir deutlich überlegen,
in zweien gleichauf, in zweien chancenlos.** Der wichtigste Befund ist keiner
dieser sechs, sondern dass Meshy seit kurzem in unserem Feld steht — und der
zweitwichtigste, dass die Kette *dort erzeugen, hier druckfertig machen* heute
schon vollständig funktioniert, ohne dass eine Zeile dafür geschrieben werden
müsste. Sie ist nur nirgends aufgeschrieben.

**Verhältnis zu den bestehenden Konzepten.** `konzept-wettbewerb-2026-08.md`
(11.08.) zieht das Feld in sechs Gruppen auf und behandelt die KI-Generatoren
als Gruppe G6 — in einer Tabellenzeile und in Abschnitt 2.4. Dieses Dokument
vertieft die zwei Vertreter, die der Auftrag nennt, und korrigiert **eine
Aussage von gestern**: Die Abgrenzung „unsere Rolle beginnt hinter deren
Ausgabe" (§42) stimmt weiter als Absicht, beschreibt den Markt aber nicht
mehr. `konzept-bedienung.md` ist die Durchsicht der eigenen Oberfläche; die
Befunde dort werden hier **nicht** wiederholt (Doku-Doktrin, Regel 3), Teil 4
prüft nur, was der Vergleich *zusätzlich* zeigt.

**Methode.** Der eigene Stand ist aus dem laufenden Code gemessen: Register
über `load_operations()` (ohne den Aufruf fehlen sechzehn Operationen),
Handbuch über `manual.pages()`, Wissensbestand aus den TOML-Tabellen, die
Farbkette über einen eigens gefahrenen Durchlauf (Teil 3.4). Alle sechs
Bildschirmfotos des Handbuchs wurden angesehen, nicht nur eines. Der
Marktstand kommt von den Seiten der Anbieter, abgerufen am 12.08.2026:
Produktseiten, Preisseiten, `llms.txt` und `llms-full.txt` der
Dokumentation. Preise und Nutzerzahlen sind ihre Angaben, keine geprüften
Werte. Wo etwas nicht messbar war, steht „nicht geprüft".

**Eine Einordnung vorweg, damit der Vergleich fair bleibt:** Solidon 1.0 ist
noch nicht erschienen (Website: „Version 1.0 erscheint 2026"). Verglichen wird
ein fertiges, unveröffentlichtes Programm mit zwei laufenden Diensten, die
zusammen zweistellige Millionenzahlen an Nutzern melden. Wo unten „chancenlos"
steht, ist das keine Schwäche des Produkts, sondern der Größenunterschied.

---

## Teil 1 — Was die beiden heute sind

### 1.1 Meshy

Ein KI-Generator, der Text und Bilder in Netze verwandelt — und, das ist neu,
ein vollständiger 3D-Druck-Arbeitsablauf drumherum.

| | |
|---|---|
| **Geschäftsmodell** | Abo mit Guthaben. Frei: 100 Guthaben/Monat, Ergebnis unter CC BY 4.0. Pro 20 $/M (1.000 Guthaben), Premium 40 $, Ultra 100 $, Studio 70 $ (+10 $ je Mitglied), Enterprise auf Anfrage. Ab Bezahlplan gehören die Ergebnisse dem Nutzer. |
| **Erzeugen** | Text→3D, Bild→3D, Mehrbild→3D, Stapelverarbeitung, KI-Texturierung, PBR-Satz (Albedo/Normal/Metallic/Roughness), HD-Textur in 4K |
| **Nachbearbeiten** | Remesh, UV-Unwrap, Retexture, Texture Edit, Low-Poly mit gesteuerter Polygonzahl, Auto-Rigging (humanoid und vierbeinig), Animation mit über 600 Bewegungsvorlagen, Scene Compose, KI-Video |
| **3D-Druck** | Druckbarkeitsprüfung, Auto-Reparatur, **Auto Split**, Mehrfarbdruck (bis 16 Farben, Ausgabe 3MF), Übergabe an acht Slicer |
| **Kreativlabor** | Fertigteile in zwei Stufen (Entwurf, dann Bau): Schlüsselanhänger, Kühlschrankmagnet, Figur, Vinylfigur, Klemmbaustein-Figur, Lampe, Tastenkappe. Der Schlüsselanhänger nimmt `badge_shape`, `size_mm` (0–400), `relief_height_mm` (0–20), `base_thickness_mm` — also echte Millimeter. |
| **Schnittstelle** | REST mit Playground, Authentifizierung, Webhooks, SSE, Ratenbegrenzung, Changelog — **und ein eigener MCP-Server** |
| **Ökosystem** | Erweiterungen für Bambu Studio, Creality Print, OrcaSlicer, Cura, **Elegoo Slicer**, Lychee, Snapmaker, Flash Studio, dazu Blender, Unity, Unreal, Godot, Maya, 3ds Max, Roblox. Veröffentlichen nach MakerWorld, Printables, Thingiverse. Druckservice mit Versand. |
| **Größe** | Eigene Angabe: 100 Mio. erzeugte Modelle, 12 Mio. Nutzer, 10 Mio. Besuche im Monat, G2 und Trustpilot je 4,8 |

Der Werbesatz auf der Startseite lautet sinngemäß, Meshy sei die einzige 3D-KI,
die fürs Drucken trainiert wurde — wasserdicht, mannigfaltig, beim ersten
Versuch bereit zum Slicen.

**Ein Detail mit Gewicht:** Erzeugte Dateien werden nach **drei Tagen**
gelöscht, außer bei Enterprise. Wer dort arbeitet, hat 72 Stunden, um
herunterzuladen. Das steht in ihrer eigenen Dokumentation unter „Asset
Retention" und ist die härteste Einzelaussage, die dieses Dokument über die
Gegenseite enthält.

### 1.2 Hyper3D Rodin

Derselbe Kern, andere Zielgruppe: Rodin geht auf Produktionspipelines und
Unternehmen, nicht auf den Drucker.

| | |
|---|---|
| **Geschäftsmodell** | Frei 0 $ (Einzelkauf 1,50 $/Guthaben), Creator 30 $/M (~60 Modelle), Business 120 $/M (~416 Modelle, API mit 120–240 Anfragen/Minute, 4K-Texturen), Enterprise mit privater Installation und eigenem LoRA. Bildungstarif. |
| **Stärke** | Tempo und Auflösung: Gen-2.5 nennt ~4 s für die Geometrie, ~5 s für das ganze Modell, über 10 Mio. Polygone |
| **Kontrolle** | **3D ControlNet** — Erzeugung wird über Hüllquader, Voxel oder Punktwolke geführt. Iteratives Aufteilen in bearbeitbare Teile, partielle Bearbeitung ausgewählter Bereiche, Smart Low-Poly. Fünfstufiger Aufwandsregler mit Zeitangabe (~4 s bis ~80 s). |
| **Werkzeugkasten** | OmniCraft: HDRI-Erzeuger, Texturerzeuger, Bild- und Videoerzeuger, SVG→3D, Mesh-Editor, KI-Avatare |
| **Unternehmen** | SSO über SAML 2.0, Identity-Provider-Anbindung, domänenbasierter Zugang, Teams und Rollen, geteilte Asset-Arbeitsbereiche, Prüfprotokolle |
| **3D-Druck** | Nur als Anwendungsfall genannt, plus STL im Export. Keine Druckbarkeitsprüfung, keine Slicer-Anbindung, kein Mehrfarbdruck. |

### 1.3 Der Befund, aus dem alles andere folgt

Von den beiden ist **Hyper3D der ungefährlichere**. Rodin baut Assets für
Spiele, Film und Produktvisualisierung; der Drucker ist eine Fußnote. Wer dort
ein Teil erzeugt, das an eine vorhandene Kante passen soll, bekommt Polygone,
keine Maße.

**Meshy dagegen steht seit kurzem auf unserem Feld.** Sechs ihrer Funktionen
heißen fast wörtlich wie unsere:

| Meshy | Solidon |
|---|---|
| Analyze Printability | Prüfbericht, Analysekarten |
| Repair Printability | Op `repair`, Reparaturkette |
| **Auto Split** | Ops `split_plane`, `split_pinned` — im Menü „Automatisch teilen" |
| Multi-Color Print (bis 16 Farben, 3MF) | Op `slots_from_texture`, 3MF mit Materialgruppen |
| 3D Agent im Chat | Agentenschicht, Chat |
| Übergabe an Elegoo Slicer | `export/handover.py`, `slicer_keys.py` |
| MCP-Server | Fernsteuerung über MCP |

Das ist kein Zufall und keine Kopie in eine Richtung — es ist derselbe
naheliegende Arbeitsablauf, den beide gefunden haben. Die Folge ist trotzdem
unangenehm: **Der Satz „wir fangen an, wo die Generatoren aufhören" ist als
Abgrenzung nicht mehr selbsterklärend.** Ein Kunde, der beide Seiten sieht,
liest zweimal dieselbe Versprechung. Der Unterschied ist real und groß, aber
er muss ab jetzt *gezeigt* werden, statt behauptet — und zwar an den Stellen,
wo die Namen gleich sind und die Sache verschieden ist. Teil 3 macht das
Paar für Paar.

---

## Teil 2 — Erzeugen: der Bereich, den wir verlieren

| | Meshy | Rodin | Solidon |
|---|---|---|---|
| Text→Netz | ja, unter 1 min | ja, ~5 s | über ComfyUI, lokal, Hunyuan3D 2.1 |
| Bild→Netz | ja | ja, mit Multi-View | ja, dasselbe Backend |
| Steuerung der Form | Prompt | **Hüllquader, Voxel, Punktwolke** | Prompt |
| PBR-Texturen | 4K | 4K | nein |
| Rigging, Animation | ja, 600 Vorlagen | Avatare | nein, und nie |
| Voraussetzung | Konto und Guthaben | Konto und Guthaben | **eigene Grafikkarte, ComfyUI installiert** |

Gegen zwei Häuser mit Kapital und eigenen Modellen gewinnen wir diesen Punkt
nicht, und der Bauplan sagt das selbst (§42): generierte Netze sind maßlich
wertlos, unsere Rolle beginnt danach. Die Website ist an dieser Stelle bereits
ehrlich — Weg 3 nennt die Voraussetzung („kräftige Grafikkarte") und sagt
dazu, dass Weg 1 und 2 ohne sie vollständig nutzbar bleiben. Das ist die
richtige Haltung und muss nicht geändert werden.

**Eine Idee der Gegenseite verdient trotzdem Aufmerksamkeit.** Rodins
ControlNet über Hüllquader ist der einzige Ansatz im ganzen Feld, der
Erzeugung und Maß zusammenbringt: Wer eine Box vorgibt, in die das Ergebnis
passen muss, bekommt ein Ergebnis, das hineinpasst. Das ist nahe an dem, was
ein Druckteil braucht, und es ist die einzige Stelle, an der die
Generatoren-Welt unser Kernproblem berührt. Ob unser ComfyUI-Weg so etwas
kann, ist **nicht geprüft** (Befund B10).

---

## Teil 3 — Wo die Namen gleich sind: sechs Paare im Detail

Das ist der Kern dieses Dokuments. Sechsmal derselbe Name, sechsmal eine
andere Sache.

### 3.1 „Druckbarkeit prüfen" — fünf Werte gegen vierzehn

**Was Meshys `analyze-printability` prüft** — aus ihrer eigenen
Dokumentation, Endpunkt kostenlos:

- wasserdicht ja/nein
- Volumen
- nicht-mannigfaltige Kanten
- degenerierte Flächen
- Löcher (Randschleifen)

Dazu ein Gesamturteil („healthy", „warning", „error", „unknown") und Zähler.
Und dann steht dort, ebenfalls in ihrer Dokumentation, der Satz, der die Sache
entscheidet: geprüft wird **nicht** auf Wandstärke, Überhänge, dünne Teile
oder Stützbedarf.

**Was wir prüfen** — Module und Funktionen aus dem Code:

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

Dazu eine Unterscheidung, die es dort gar nicht gibt: Regel 14 verlangt, dass
Kennzahlen aus Schichtanalyse und aus G-Code nie vermischt werden und die
Herkunft immer ausgewiesen wird. Meshy nennt eine Zahl und sagt nicht, woher.

**Was wir von ihrer Darstellung lernen können.** Ihr Ergebnis ist ein
Kennzahlenblock: *Wasserdicht: Ja · Volumen: 702,19 cm³ · Löcher: 0 ·
Non-Manifold-Kanten: 0.* Unser Prüfbericht (Bildschirmfoto `report.png`) ist
eine Liste von Sätzen: „Das Modell ist an drei Stellen offen", „14 Dreiecke
zeigen nach innen", darüber „0 × Fehler · 2 × Warnung · 2 × Hinweis". Unsere
Form ist für den Laien besser, weil jeder Satz einen Handlungsvorschlag trägt
(Regel 17). Ihre ist besser zum Vergleichen und zum Weitergeben. Beides
zugleich ginge: ein schmaler Kennzahlenkopf über der Befundliste — wasserdicht,
Volumen, Komponenten, schmalste Wand, schlimmster Überhang. Die Werte liegen
alle vor (Befund B9).

### 3.2 „Auto Split" — trennen gegen trennen und verbinden

Meshy beschreibt es auf der Startseite so: Ist ein Modell zu komplex, zerlegt
Auto Split es in wasserdichte Teile, die bereits auf dem Druckbett angeordnet
sind. In ihrer **Dokumentation kommt Auto Split nicht vor** — weder in der
Endpunktliste noch im Volltext (`llms-full.txt` geprüft). Es ist eine beworbene
Funktion ohne Handbuchseite.

Bei uns sind es zwei Operationen: `split_plane` trennt an einer Ebene,
`split_pinned` trennt **und verstiftet**. Die Website formuliert es so: „Auto-Split
legt Passstifte, Bohrungen und die zugehörigen Passungen gleich mit an."

Der Unterschied ist der ganze Punkt des Teilens: Zwei Hälften, die man
zusammenkleben soll, brauchen eine Führung. Ihre Version liefert zwei Hälften,
unsere liefert zwei Hälften, die ineinanderfinden — mit einem Spiel, das aus
dem Materialprofil kommt und nicht geschätzt ist.

### 3.3 „Mehrfarbdruck" — und was dabei herauskommt

| | Meshy `multi-color-print` | Solidon `slots_from_texture` |
|---|---|---|
| Eingang | GLB oder FBX über URL, oder eine eigene Aufgaben-ID | jedes geladene Objekt |
| Farbzahl | `max_colors` 1–16, Vorgabe 4 | Zahl der **tatsächlich eingelegten** Filamente |
| Verfahren | nicht dokumentiert | Quantisierung mit Startwert, Glättung über Nachbarflächen, unbedeutende Gruppen fallen weg |
| Wiederholbar | nicht zugesichert | ja — Startwert aus der Operation, beim erneuten Öffnen dasselbe Ergebnis (§11.3) |
| Zu wenig Farben im Modell | nicht dokumentiert | eigener Befund: „Weniger Farben als Filamente — mehr gibt das Modell nicht her" |
| Ausgang | 3MF | 3MF mit Materialgruppen, dazu Prüfung der Filamentwechsel |
| Kosten | 10 Guthaben je Lauf | keine |
| Ort | ihr Server | dieser Rechner |

### 3.4 Die Kette, die schon funktioniert — gemessen

Der erste Durchgang ließ offen, ob Farbinformation aus einer Generator-Ausgabe
bei uns ankommt. Sie tut es. Nachgefahren am 12.08.2026 mit einer
GLB-Szene aus drei verschieden gefärbten Körpern — so, wie ein Generator
ausliefert:

| Schritt | Ergebnis |
|---|---|
| `read_mesh(glb)` | 1.304 Dreiecke, **0 Materialslots**, Farben als `ColorVisuals` erhalten |
| `to_slots(..., 3 Filamente)` | 3 Slots, 1.304 Flächenzuweisungen, Farben zurückgewonnen: (0,86 / 0,12 / 0,12), (0,12 / 0,24 / 0,86), (0,94 / 0,78 / 0,16) — exakt Rot, Blau, Gelb der Vorlage |
| `to_slots(..., 4 und 8 Filamente)` | weiterhin 3 Slots — das Modell gibt nicht mehr her, genau der vorgesehene Befund |
| `export_bytes(..., "3mf")` | 13.098 Bytes |
| zurückgelesen | 1.304 Dreiecke, 1.304 Flächenzuweisungen, Slots [0, 1, 2] — verlustfrei |

**Das ist die Antwort auf die wichtigste offene Frage des ersten Durchgangs,
und sie ist besser als erhofft.** Die Kette *Meshy oder Rodin erzeugt → Solidon
macht druckfertig* läuft heute, ohne eine Zeile neuen Code. Was Meshy für 10
Guthaben auf ihrem Server rechnet, rechnet Solidon lokal, mit den Filamenten,
die tatsächlich in der Maschine stecken, und wiederholbar.

Ein Zwischenschritt fehlt zur Bequemlichkeit: Nach `read_mesh` steht
`slots = 0`, die Umrechnung ist ein eigener Menüpunkt. Wer eine bunte GLB
öffnet, sieht zunächst ein farbiges Objekt ohne Filamentzuordnung. Ein Hinweis
im Prüfbericht — „Dieses Objekt trägt Farben, aber keine Filamentzuordnung.
Umrechnen?" — schließt die Lücke mit einem Befund statt mit einer Funktion
(Befund B3).

### 3.5 „Übergabe an den Slicer" — Datei öffnen gegen Profil schreiben

Meshys Erweiterungen öffnen das Modell im Slicer. Acht Programme, ein Klick,
funktioniert.

Unser `handover.py` tut etwas anderes: Es kennt drei Profilfamilien —
`prusa`, `orca`, `cura` (`slicer_keys.py:25`) — **liest den Profilbestand der
installierten Anwendung** (`slicer_profiles.py`: Pfad, Name, Druckermodell,
Düse, kompatible Drucker, Filamenttyp, Abstammung, und ob ein Profil vom
Nutzer selbst angelegt wurde) und schreibt die aus der Geometrie abgeleiteten
Einstellungen in die richtigen Schlüssel dieser Familie. Selbst angelegte
Profile gewinnen bei Gleichstand, „weil jemand sie absichtlich gemacht hat".

Die drei Familien decken praktisch das Feld: Die Orca-Familie umfasst
OrcaSlicer, Bambu Studio, Creality Print und ElegooSlicer; PrusaSlicer und
CuraEngine stehen daneben. Was uns fehlt, ist nicht die Abdeckung, sondern der
Klick aus der Gegenrichtung — eine Erweiterung *im* Slicer, die Solidon
aufruft. Das ist ein Ökosystem-Punkt, kein technischer (Teil 5).

### 3.6 „Agent" und „MCP" — Aufträge im Dienst gegen Hände am offenen Dokument

Hier war der erste Durchgang zu grob: Ich schrieb von „zwei unvereinbaren
Modellen, REST gegen MCP". Meshy betreibt **selbst einen MCP-Server**. Die
Technik ist dieselbe; verschieden ist, was am anderen Ende steht.

| | Meshy MCP | Solidon MCP |
|---|---|---|
| Was die Werkzeuge tun | Aufträge im Dienst anlegen: erzeugen, remeshen, retexturieren, riggen, animieren; Status abfragen, herunterladen | Operationen auf dem **gerade geöffneten Dokument** ausführen |
| Verkettung | über `input_task_id`: erzeugen → verfeinern → texturieren → riggen | über den Operationsstapel, der ohnehin da ist |
| Zustand | Aufgaben auf ihrem Server, **nach 3 Tagen gelöscht** | die Projektdatei auf dieser Platte |
| Rücknahme | Aufgabe abbrechen | Strg+Z im Fenster; der Verlauf zeigt, dass es von außen kam |
| Erreichbarkeit | das Internet | `127.0.0.1`, standardmäßig **aus** |
| Kosten je Aufruf | 1–50 Guthaben | keine |
| Was nicht hindurchgeht | — | OpenSCAD-Quelltext und alles, was wie ein Dateipfad aussieht (Regeln 11, 12, 13) |
| Grenzen | 20 Anfragen/s, 10–100 gleichzeitige Aufgaben je Tarif | keine |
| Dokumentiert | vollständige Werkzeugliste mit Namen | **eine Handbuchseite, 980 Zeichen, ohne Werkzeugliste** |

Ihr MCP ist eine Fernbedienung für eine Fabrik. Unserer ist eine zweite Hand
am selben Werkstück. Beide sind legitim; nur unsere lässt ein anderes Programm
an einem Modell weiterarbeiten, das gerade auf dem Bildschirm liegt.

Die Dokumentationslücke ist die auffälligste des ganzen Handbuchs: Sie haben
jedes Werkzeug benannt, wir haben keines (Befund B6).

---

## Teil 4 — Design und Oberfläche

Die Frage war, ob wir mithalten. Sie lässt sich nicht mit ja oder nein
beantworten, weil zwei verschiedene Dinge verglichen werden: eine Webanwendung,
die Ergebnisse ausstellt, und ein Werkzeugfenster, das Arbeit ermöglicht. Für
diesen Durchgang wurden alle sechs Bildschirmfotos angesehen, nicht nur das
Hauptfenster — und das ändert das Urteil an zwei Stellen.

### 4.1 Was ihre Oberflächen tun

Beide sind nach demselben Muster gebaut:

- **Das Ergebnis steht im Mittelpunkt.** Galerien mit Vorschaubildern, Likes,
  Namen der Ersteller. Rodin sortiert nach Charaktere, Sci-Fi, Fantasy, Möbel,
  Fahrzeuge; Meshy zeigt eine endlose Kachelwand.
- **Ein Eingabefeld, ein Knopf.** Der Kernweg ist „beschreiben, drücken,
  warten".
- **Wartezeit wird zur Ware.** Rodin lässt die Rechenzeit wählen — fünf Stufen
  von ~4 s bis ~80 s — und macht daraus ein Bedienelement statt eines
  Ärgernisses.
- **Sozialer Beweis überall.** Nutzerzahlen, Bewertungen, Zitate,
  Kundengeschichten.

### 4.2 Was unsere Oberfläche tut — differenzierter als im ersten Durchgang

Der erste Durchgang sah nur das Hauptfenster und schloss daraus: „wir zeigen
Werkzeuge, sie zeigen Ergebnisse". **Das war zu grob.** Zwei der sechs
Ansichten sind bildstark:

- **Startbildschirm** (`start-screen.png`): Ablagefeld für Dateien, darunter
  acht Beispielprojekte als Karten mit gerendertem Vorschaubild, Titel und
  einem Satz, was daran zu sehen ist — „Weg 1 — fremdes Modell anpassen",
  „Kalibrieren — einmal drucken, dann stimmt es". Das ist derselbe Kartenaufbau
  wie ihre Galerie, nur mit unseren Inhalten statt fremder Kunst.
- **Bausteinkatalog** (`catalog.png`): gerenderte Vorschauen in Gruppen, mit
  Suchfeld, und einer Farbkodierung, die Regel 18 einhält — orange eingefärbte
  Bausteine tragen zusätzlich den Text „– nimmt Material weg". Visuell der
  stärkste Bildschirm der Anwendung.

Bleiben drei echte Befunde:

**4.2.1 Das Hauptfenster zeigt Text, wo Bild ginge.** Im Objektbaum stehen
„Dose" und „Dose Deckel" als Zeilen mit Maßen. Die Renderstrecke für
Vorschaubilder existiert und wird im Katalog bereits benutzt; im Objektbaum
nicht (Befund B8).

**4.2.2 Das Modell ist grau.** Ein einfarbig graues Teil in einem grauen Raum.
Für Geometrie korrekt, für den ersten Eindruck teuer: Jeder Vergleich, den ein
Interessent nebeneinanderlegt, zeigt links eine texturierte Figur und rechts
einen grauen Kasten. Die Analysekarten und die Schichtenvorschau *sind* unser
farbiges Bild — sie gehören ins Marketingmaterial nach vorn (Befund B2).

**4.2.3 Der Operationsdialog hat Platz für etwas, das fehlt.** Im
Bohrungsdialog (`op-dialog.png`) stehen über dem Beschreibungssatz rund
90 Pixel leerer Fläche, darunter vier Felder mit Einheit und `fx`-Knopf für
Ausdrücke, dann „Weitere Einstellungen". Der Aufbau ist richtig (§2.4:
Vorderseite zwei bis drei Werte). Der Leerraum oben ist entweder eine
weggelassene Vorschau oder ein zu hoher Dialog — beides lohnt einen Blick. Bei
den Generatoren zeigt jede Eingabe sofort ein Bild.

**4.2.4 Was der Vergleich bestätigt, statt es zu kritisieren:** Der
Skizzeneditor (`sketch-mode.png`) ist ein vollwertiger Zwangs-Löser —
Bedingungsliste mit Deckung, Waagerecht, Senkrecht, Abstand, Fest, und unten
die Zeile „Ein Freiheitsgrad ist noch frei". Davon existiert bei Meshy und
Rodin nichts, nicht ansatzweise. Das ist kein Feld, auf dem verglichen wird —
es ist ein Feld, das sie nicht betreten.

**4.2.5 Wartezeit ist bei uns ein Zustand, bei Rodin ein Regler.**
`ctx.quality` kennt Entwurf und Fein. Im Fenster ist das eine Einstellung, kein
Angebot. Rodins fünfstufiger Aufwandsregler mit Sekundenangaben ist dieselbe
Sache, als Versprechen formuliert (Befund B11).

### 4.3 Was wir nicht übernehmen

Galerie, Likes, Community-Kachelwand, Kontozwang, endloses Scrollen. Das
verlangt einen Dienst, ein Konto und Serverbetrieb — alle drei stehen auf der
Liste dessen, was ausdrücklich nicht gebaut wird. Der Verzicht ist kein
Nachteil, der ausgeglichen werden muss; er ist die Zusage „kein Konto, kein
Abo", die auf der eigenen Preisseite steht.

---

## Teil 5 — Handbuch gegen `docs.meshy.ai`

Die Frage war, ob unser Handbuch alles so detailliert beschreibt. Beide Seiten
gemessen:

| | Meshy-Doku | Solidon-Handbuch |
|---|---|---|
| Aufbau | vier Pfade: Web App, API, Plugins, 3D Printing | 20 geschriebene Seiten + 15 aus dem Register erzeugte Referenzseiten |
| Umfang | nicht messbar (gehostet) | ~110.000 Zeichen, ~19.600 Wörter |
| Abbildungen | Quick Start **ohne Bilder** | 32 Verweise, 25 Abbildungen im Katalog, 6 Bildschirmfotos je Sprache |
| Sprachen | Englisch | Deutsch und Englisch, beide vollständig |
| Funktionsreferenz | von Hand gepflegt, ~20 Funktionen | **erzeugt, alle 77 Operationen mit Parametern, Grenzen, Einheiten** |
| Glossar | ja | ja („Wörterbuch", 3.330 Zeichen) |
| Fehlerbehebung | Tabelle je Seite | eine Seite (2.760 Zeichen), ohne Wortlaut der Meldungen |
| FAQ | je Seite | nur auf der Website |
| Changelog | ja, für Webapp und API | **nein** |
| Anleitung zum Prompting | eigene Seite | **nein** |
| Anwendungsfälle als Anleitung | Game Assets, 3D Printing | **nein** |
| Werkzeugliste der Fernsteuerung | vollständig | **nein** |
| Beworbene Funktion ohne Doku | **Auto Split** | — |
| Suche | ja | ja, in `handbuch.html` |
| Lernmaterial daneben | Blog, Anleitungen, 3D-Druck-Akademie, Kundengeschichten, Hilfezentrum | keins |

### 5.1 Wo wir strukturell besser sind

Die erzeugte Referenz ist ein Vorteil, den sie nicht einholen können, ohne ihre
Dokumentation neu zu bauen. Bei uns kann keine Operation undokumentiert
existieren — Regel 4 verbietet den Registereintrag ohne übersetzte Texte, und
die Handbuchseite entsteht aus demselben Eintrag. Ihre Funktionsseiten sind
Handarbeit und veralten einzeln; ihr eigenes Auto Split ist der Beweis: beworben,
nicht dokumentiert.

Dazu Bilder, wo ihr Quick Start keine hat, und zwei vollständige Sprachen.

### 5.2 Wo wir schlechter sind — und der Befund, den ich nicht erwartet hatte

Unsere geschriebenen Seiten sind **Fließtext**, zwischen 980 und 6.177 Zeichen,
im Schnitt ~2.100. Gut geschrieben, aber ohne die Formen, die beim Nachschlagen
tragen: kein „Kurz gesagt", keine nummerierten Abläufe, keine Fehlertabelle mit
der wörtlichen Meldung in der linken Spalte. Wer im Programm eine Meldung liest
und im Handbuch danach sucht, findet den Wortlaut heute nicht.

**Und dann der Fund, der beim zweiten Durchgang auffiel.** Ich habe die
Handbuchseiten nach Zahlenwerten durchsucht — Millimeter, Grad, Prozent:

| Seite | gefundene Werte |
|---|---|
| Hinsehen, bevor gedruckt wird | **keine** |
| Auf die Platte und hinaus | **keine** |
| Wenn das Teil nicht auf die Platte passt | **keine** |
| Wenn etwas nicht geht | **keine** |
| Material, Toleranzen, Passungen | „5 mm", „45 Grad" |

Zwei Zahlen im ganzen erzählenden Teil. Meshys Dokumentation nennt ebenfalls
**keinen einzigen** Wert für Wandstärke, Überhangwinkel, Stützen, Orientierung
oder Toleranzen — das wurde im Volltext geprüft. Beide Handbücher sind an
dieser Stelle gleich wertfrei.

Der Unterschied ist, dass **wir die Werte haben und sie nicht.** Im Programm
liegen:

- **6 Materialprofile** (PLA, PETG, PETG-CF, ASA, ABS, TPU-95A) mit `clearance`,
  `press`, `shrinkage`, `elephant_foot`, `hole_compensation`, `calibrated`
- **16 Druckerprofile** ab Werk (Bambu A1/A1 mini/P1S/X1C, Creality Ender-3 V3
  und K1, Anycubic Kobra 2, Elegoo …)
- **40 Normteilmaße** (Angabe der Website, aus `standards.toml`)
- **11 Konstruktionsregeln**, Version 2, mit Titel und Begründung:
  Mindestwandstärke, Fasen statt Überhängen, Toleranzen aus dem Materialprofil,
  Hauptmaße als Parameter, Überlappung bei Booleschen Ops, Löcher größer als
  Nennmaß, Erste Schicht, OpenSCAD-Auflösung, Bausteine vor Primitiven, eigener
  Kern vor OpenSCAD, Fragen vor Raten

Das ist kodifiziertes Fertigungswissen — genau das, wofür Meshy eine
„3D-Druck-Akademie" als Blogstrecke betreibt. Bei uns rechnet das Programm
daraus, und der Nutzer bekommt es nie zu lesen.

Zwei erzeugte Handbuchseiten — „Die Regeln, nach denen Solidon urteilt" und
„Was in den Material- und Druckerprofilen steht" — kosten wenig (dieselbe
Technik wie die Op-Referenz), veralten nie, und sind das einzige Kapitel, das
die Gegenseite strukturell nicht schreiben kann: Ihre Werte stehen in keinem
Programm (Befund B4). Der Bauplan nennt die Regelsammlung in §39 ohnehin „das
eigentliche Produkt". Ein Produkt, das man nicht lesen kann, ist schwer zu
verkaufen.

---

## Teil 6 — Preis, Eigentum und Dauer

| | Meshy | Rodin | Solidon |
|---|---|---|---|
| Testen | 0 $ dauerhaft, 100 Guthaben/M, Ergebnis CC BY 4.0 | 0 $, Vorschau vor Bestätigung | **14 Tage vollständig** |
| Arbeitstarif | 20 $/M = 240 $/J | 30 $/M = 360 $/J | **49 € einmalig** (später 79 €) |
| Nach zwölf Monaten | 240 $ gezahlt | 360 $ gezahlt | 49 € gezahlt, Programm läuft |
| Nach Kündigung | Zugang endet | Zugang endet | läuft weiter, alle 1.x-Updates inklusive |
| Ergebnisse | **nach 3 Tagen gelöscht** (außer Enterprise) | unbegrenzt privat ab Bezahlplan | Datei auf der eigenen Platte |
| Rechnet ab | Guthaben je Aufruf (1–50) | Guthaben je Modell | nichts |
| Offline | nein | nein | **ja** |

Das ist nach der Druckbarkeitsprüfung unser stärkstes Argument, und es steht
auf der Website als Zahl statt als Rechnung. „49 € einmalig gegen 240 $ im
Jahr" versteht jeder; „49 € zur Einführung, später 79 €" ist eine Preisangabe.

Die Drei-Tage-Löschung gehört danebengestellt — nicht als Spitze, sondern als
Sachverhalt mit Quelle. Sie beantwortet die Frage, die jeder Käufer eines
Einmalprodukts still mitdenkt: *Was habe ich hinterher in der Hand?*

Ein Punkt gegen uns, der ehrlich dazugehört: Beide haben eine **dauerhaft**
kostenlose Stufe. Unsere vierzehn Tage sind eine Testphase, kein Dauerangebot.
Wer heute vergleicht, kann dort ohne Frist anfangen.

---

## Teil 7 — Können wir mithalten?

| Bereich | Urteil |
|---|---|
| **Druckbarkeit und Fertigungsurteil** | **deutlich überlegen** — fünf Topologiewerte gegen vierzehn Sachverhalte samt Fertigung |
| **Konstruieren mit Maß** | **konkurrenzlos** — Stapel, Parameter, Zwänge, Passungen, Normteile; auf der Gegenseite existiert nichts davon |
| **Mehrfarbe und Aufbereitung generierter Netze** | **gleichauf bis überlegen** — Kette gemessen, lokal, wiederholbar, ohne Guthaben |
| **Handbuch** | **überlegen** in der Referenz, **gleichauf** in der Prosa (beide wertfrei), **unterlegen** in Form und Auffindbarkeit |
| **Erzeugen aus Text und Bild** | **chancenlos** — und nach §42 nicht unser Rennen |
| **Reichweite, Ökosystem, Integrationen** | **chancenlos** — 12 Mio. Nutzer gegen einen Einzelentwickler vor Version 1.0 |
| **Preis und Eigentum** | **überlegen**, wird nicht ausgespielt |
| **Erster optischer Eindruck** | **unterlegen** im Hauptfenster, **gleichauf** bei Startbildschirm und Katalog |

Der Satz, der aus den ersten drei Zeilen folgt:
*Meshy erzeugt Dinge, die aussehen wie etwas. Solidon macht Teile, die passen —
auch die, die Meshy erzeugt hat.*

---

## Teil 8 — Was der zweite Durchgang korrigiert hat

Vier Aussagen der ersten Fassung waren falsch oder zu grob. Sie stehen hier,
weil eine Konzeptvorlage, die ihre eigenen Irrtümer verschweigt, beim nächsten
Lesen nicht mehr zu prüfen ist.

1. **„Ob Farben beim GLB-Import ankommen, ist nicht geprüft."** Jetzt gemessen:
   Sie kommen an, und die ganze Kette bis zur 3MF-Datei mit Materialgruppen
   funktioniert (3.4). Aus der größten offenen Frage wurde das stärkste
   Einzelergebnis.
2. **„Zwei unvereinbare Modelle: REST gegen MCP."** Falsch — Meshy betreibt
   selbst einen MCP-Server. Der Unterschied liegt nicht in der Technik, sondern
   darin, was am anderen Ende steht (3.6).
3. **„Keine kostenlose Stufe."** Falsch — 14 Tage vollständiges Testen. Der
   Unterschied bleibt (deren freie Stufe ist dauerhaft), die Darstellung war
   schief (Teil 6).
4. **„Wir zeigen Werkzeuge, sie zeigen Ergebnisse."** Zu grob, weil nur das
   Hauptfenster angesehen worden war. Startbildschirm und Bausteinkatalog
   arbeiten bereits mit gerenderten Karten (4.2).

Dazu zwei Zahlen: Die Regelsammlung hat **11** Regeln, nicht 13 — die erste
Zählung hatte andere Tabellen mitgezählt.

---

## Teil 9 — Befunde

Nummeriert, mit Priorität und Aufwand. Was daraus beschlossen wird, wandert
nach `ROADMAP.md` — dieses Dokument beschließt nichts.

### B1 — Die Vergleichstabelle Druckbarkeit fehlt · **hoch** · klein

Ihre eigene Dokumentation sagt, dass Wandstärke, Überhänge, dünne Teile und
Stützbedarf nicht geprüft werden. Das ist ein Beleg, kein Werbespruch, und er
gehört auf die Website und in die Handbuchseite „Hinsehen, bevor gedruckt
wird" — als Tabelle, welche Frage welches Werkzeug beantwortet, mit Datum und
Quelle.

### B2 — Die Analysekarten müssen nach vorn · **hoch** · klein

Unser farbiges Bild sind Analysekarten und Schichtenvorschau, nicht das graue
Modell. Ein Bild, das eine Überhangkarte neben dem fertig gedruckten Teil
zeigt, sagt in einer Sekunde, was drei Absätze nicht sagen.

### B3 — Die Kette für generierte Netze sichtbar machen · **hoch** · klein

Sie funktioniert (3.4), sie ist nur unsichtbar. Drei Schritte:

1. Ein Befund im Prüfbericht, wenn ein Objekt Farben trägt, aber keine
   Filamentzuordnung — mit der Umrechnung als Handlungsvorschlag (Regel 17).
2. Eine Handbuchseite „Ein erzeugtes Modell druckfertig machen", die den in
   3.4 gefahrenen Weg beschreibt.
3. Auf der Website ein Satz bei Weg 3, der die Generatoren beim Namen nennt.
   Wer bei Meshy erzeugt, sucht danach nach genau diesem Werkzeug.

### B4 — Das Fertigungswissen ins Handbuch heben · **hoch** · mittel

Zwei erzeugte Seiten aus `rules.toml`, `materials.toml`, `printers.toml`,
`standards.toml`: die 11 Regeln mit Begründung, die 6 Materialprofile mit
ihren Toleranzen, die 16 Druckerprofile, die 40 Normteilmaße. Dieselbe Technik
wie die Op-Referenz, veraltet nie — und das einzige Kapitel, das die
Gegenseite strukturell nicht schreiben kann. §39 nennt die Regelsammlung „das
eigentliche Produkt"; sie ist derzeit das einzige Produkt, das niemand lesen
kann.

### B5 — Handbuchform: Kurzfassung, Ablauf, Fehlertabelle · **mittel** · mittel

Je geschriebener Seite ein „Kurz gesagt" am Anfang; wo ein Ablauf existiert,
nummerierte Schritte. Wichtiger: eine Fehlertabelle, deren linke Spalte die
**wörtliche Meldung** aus dem Programm enthält. Die Meldungen liegen als
übersetzte Texte vor — die Tabelle kann erzeugt werden statt gepflegt.

### B6 — Referenz der Fernsteuerung erzeugen · **mittel** · klein

980 Zeichen gegen ihre vollständige Werkzeugliste. Die Werkzeuge kommen aus
`registry/surfaces.py` (`tool_schemas`) — dieselbe Quelle wie die Op-Referenz.
Dazu der Satz, den sie nicht schreiben können: Was hier hereinkommt, arbeitet
am offenen Dokument und lässt sich mit einem Strg+Z zurücknehmen.

### B7 — Preisrechnung statt Preisangabe · **mittel** · klein

„49 € einmalig — Meshy Pro 240 $ im Jahr, Rodin Creator 360 $", mit Datum und
Quelle. Daneben die Drei-Tage-Löschung als Sachverhalt. Beides beantwortet
dieselbe Frage: *Was habe ich hinterher in der Hand?*

### B8 — Vorschaubilder im Objektbaum · **niedrig** · mittel

Die Renderstrecke existiert und wird im Bausteinkatalog benutzt. Sie auf
Szenenobjekte anzuwenden ist Fleißarbeit mit sichtbarer Wirkung.

### B9 — Kennzahlenkopf über dem Prüfbericht · **niedrig** · klein

Wasserdicht, Volumen, Komponenten, schmalste Wand, schlimmster Überhang — als
schmale Zeile über der Befundliste. Die Werte liegen alle vor. Ihre Darstellung
ist an dieser einen Stelle besser als unsere, und der Grund ist kein
technischer.

### B10 — Rodins ControlNet als offene Frage · **offen** · groß

Erzeugung, die in einen vorgegebenen Hüllquader hineinrechnet, ist die einzige
Idee der Gegenseite, die unser Kernproblem berührt: generierte Netze haben
keine Maße. Ob unser ComfyUI-Weg so etwas kann, ist **nicht geprüft**. Eine
Frage an den nächsten Konzeptdurchgang, keine Aufgabe.

### B11 — Qualitätsstufe als Angebot statt als Einstellung · **niedrig** · klein

`ctx.quality` gibt es. Wo eine lange Rechnung beginnt, könnte die Wahl mit
einer Zeitschätzung stehen — Wartezeitverhalten nach §2.8, als Angebot
formuliert statt als Voreinstellung.

### B12 — Leerraum im Operationsdialog prüfen · **niedrig** · klein

Rund 90 Pixel über dem Beschreibungssatz. Entweder gehört dort eine Vorschau
hin, oder der Dialog ist zu hoch. Eine Messung am laufenden Fenster
entscheidet das in fünf Minuten.

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
- **Kein Kreativlabor mit Fertigteilen** in ihrer Form (Bild hinein,
  Schlüsselanhänger heraus). Unsere Entsprechung ist die Bausteinbibliothek —
  parametrisch, maßhaltig, ohne Konto. Sie darf wachsen, aber nicht zum
  Automaten werden.
- **Kein Druckservice, keine Veröffentlichungsplattform.**

---

## Abnahme

Ein Durchgang gilt als erledigt, wenn:

1. B1 steht auf Website und Handbuchseite, mit Datum und Quellenangabe.
2. B3 ist umgesetzt: Der Befund erscheint im Prüfbericht, die Handbuchseite
   existiert, und ein Test fährt die Kette aus 3.4 gegen eine Datei aus
   `tests/data/` — GLB hinein, 3MF mit Materialgruppen heraus.
3. B4 erzeugt seine zwei Seiten aus den TOML-Tabellen; ein Test hält fest, dass
   jede Regel und jedes Materialprofil dort auftaucht.
4. B6 erzeugt seine Seite aus dem Register; ein Test hält fest, dass jedes
   Werkzeug der Fernsteuerung dort steht.
5. Die Suite ist grün: `pytest`, `ruff check`, `ruff format --check`, `mypy`.

---

*Stand 12.08.2026, zweite Fassung. Der eigene Stand ist aus dem laufenden Code
gemessen, die Farbkette eigens durchgefahren, alle sechs Bildschirmfotos
angesehen. Der Marktstand stammt von den Seiten der Anbieter; Preise,
Nutzerzahlen und Aufbewahrungsfristen sind ihre Angaben, keine geprüften
Werte.*
