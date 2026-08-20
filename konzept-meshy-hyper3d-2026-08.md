# Konzept — Solidon3D gegen Meshy und Hyper3D Rodin (12.08.2026, nachrecherchiert am 19.08.2026)

Anlass ist eine Frage in vier Teilen: *Wie stehen Oberfläche, Funktionen,
Handbuch und Schnittstelle gegen die beiden führenden KI-3D-Generatoren?
Können wir mithalten?*

**Fünfte Fassung.** Die Befunde sind abgearbeitet; was daraus wurde, steht in
Teil 10.

**Vierte Fassung.** Der erste Durchgang blieb an vier Stellen bei Vermutungen;
der zweite maß sie nach. Der dritte entstand aus der Frage, ob die Webseiten
und Funktionen wirklich vollständig angesehen worden seien — sie waren es
nicht, und eine Aussage war schlicht falsch. Der vierte kam aus einer
Beobachtung am laufenden Fenster: *Wo ist der orange Akzent? Alles eintönig.*
Sie stimmt, sie ist messbar, und sie hat den schwächsten Teil dieses Dokuments
— den Oberflächenvergleich — auf eigene Füße gestellt (4.3, 4.4, B16). Alle
sieben Korrekturen stehen in Teil 8, nicht versteckt: Eine Korrektur ist mehr
wert als eine Behauptung, die zufällig stimmte.

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

**Methode.** Der eigene Stand ist aus dem laufenden Code gemessen: **alle 77
Operationen** mit Titel und Beschreibung ausgelesen (über `load_operations()` —
ohne den Aufruf fehlen sechzehn), alle 16 Bausteine mit ihren Features, die
Wissenstabellen einzeln, das Handbuch über `manual.pages()`, die Farbkette über
einen eigens gefahrenen Durchlauf (3.4). Alle sechs Bildschirmfotos wurden
angesehen, nicht nur eines.

Der Marktstand kommt von den Seiten der Anbieter, abgerufen am 12.08.2026 —
**im dritten Durchgang über den Browser und ihre eigene Navigation** statt über
geratene Pfade: Produkt- und Preisseiten, die Dokumentationsseiten zu Auto
Split und zur Slicer-Anbindung, die Werkzeugstrecke, die Akademie, dazu
`llms.txt` und die API-Referenz. Preise, Nutzerzahlen und Aufbewahrungsfristen
sind ihre Angaben, keine geprüften Werte. Wo etwas nicht einsehbar war — die
Lektionstexte der Akademie und die Webanwendung selbst liegen hinter einem
Konto —, steht „nicht geprüft" statt einer Schätzung.

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

> **Nachrecherchiert am 19.08.2026 — die Preisstufen stimmen unverändert, und
> zwei Dinge sind dazugekommen.**
>
> **Meshy 7 ging am 10.08.2026 live**, zwei Tage vor diesem Dokument: ein
> Bild-zu-3D-Grundlagenmodell, das auf die Ausrichtung zwischen Eingabebild
> und Ergebnis zielt. Meshy 6 (18.01.2026) hatte den Low-Poly-Modus und den
> ausdrücklichen Mehrfarb-3D-Druck gebracht — Texturen werden zu sauberen
> Farbblöcken für FDM zusammengefasst.
>
> **Die Preise je Aufruf sind jetzt belegt**, und eine Zahl darin ist für uns
> die interessanteste des ganzen Dokuments: Text-zu-3D kostet 20 Guthaben,
> Textur 10 bis 15, Mehrfarbdruck 10, **Druckbarkeit prüfen kostenlos**,
> Druckbarkeit reparieren 10. Die Prüfung meldet Wasserdichtheit, nicht-
> mannigfaltige Kanten, Löcher als Randschleifen und entartete Flächen. Das
> ist die Liste, die Solidons Prüfbericht führt — bei Meshy kostet sie nichts
> und läuft über eine REST-Schnittstelle.
>
> Ausgabeformate der API: GLB, FBX, USDZ, OBJ, MTL, STL, 3MF. Topologie
> wahlweise quad-dominant oder dezimiertes Dreiecksnetz; regulärer Remesh 100
> bis 300.000 Flächen, Smart Topology 100 bis 15.000. Seit dem 08.04.2026 gibt
> es „Print with Form Now" — ein erzeugtes Modell geht direkt in den
> Fertigungsdienst von Formlabs.

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

> **Nachgeprüft am 19.08.2026 — die Preisstufen stimmen, und eine Schranke ist
> schärfer, als sie hier steht:** Den **API-Zugang gibt es erst ab Business**
> (120 $/Monat), dort mit 120 bis 240 Anfragen je Minute. Free und Creator
> haben keinen. Die kostenlose Stufe erlaubt zehn private Objekte bei
> eingeschränkter kommerzieller Nutzung; Creator kostet 30 $ im Monat
> beziehungsweise 288 $ im Jahr.

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

### 3.2 „Auto Split" — der Schnitt gegen die Verbindung

Ihre Handbuchseite (`/en/webapp/guides/3d-model/auto-split`) gelesen, nicht
zusammengefasst. Sie ist gut: Kurzfassung, Wann-benutzen, **Wann-nicht-benutzen**,
neun nummerierte Schritte, Bebilderung, Tipps, vier Fragen mit Antwort.

**Was ihres besser kann:**

- **Der Schnitt folgt der Form, nicht einer Ebene.** Ihre eigene Antwort auf
  die Frage nach dem Unterschied zum Slicer: Ein planarer Schnitt kann nur
  entlang einer flachen Ebene trennen und hinterlässt gerade Nähte quer über
  die Oberfläche; ihr Verfahren schneidet entlang der natürlichen Teilform, die
  Naht versteckt sich in der Struktur. **Das können wir nicht** — `split_plane`
  und `split_pinned` schneiden an einer Ebene.
- **Vorschau in ~40 Sekunden**, danach neu würfeln möglich (kostet Guthaben).
- **Ein Schieberegler zieht die Teile auseinander**, zwei Ansichten: zusammengesetzt
  und auf der Platte. Ein Explosionswerkzeug haben wir auch (Viewportleiste,
  „Explosion"), aber nicht als Regler im Teilungsablauf.
- Schnittflächen werden automatisch wasserdicht verschlossen, Teile auf dem
  Bett angeordnet, ein Klick in Bambu Studio, OrcaSlicer, Elegoo Slicer.

**Was in ihrer eigenen FAQ steht und die Sache dreht:**

| Ihre Aussage | Folge |
|---|---|
| „Auto Split unterstützt derzeit nur unstrukturierte Entwurfsmodelle, die mit Meshy 6 erzeugt wurden." | **Ein eigenes oder heruntergeladenes Modell geht nicht hindurch.** Der häufigste Fall überhaupt — die zu große STL aus dem Netz — ist ausgeschlossen. |
| „Geteilte Teile werden derzeit ohne Farbinformation exportiert, sie können also nicht direkt in den Mehrfarbdruck." | Teilen und Mehrfarbe schließen sich bei ihnen aus. Genau die Kombination, für die die Funktion beworben wird. |
| „Sie brauchen präzise Schnittführung oder eigene Verbindungen — die sind in Blender oder Meshmixer besser aufgehoben." | **Verbindungen sind ausdrücklich kein Teil des Werkzeugs.** Sie verweisen dafür auf fremde Programme. |

Genau dort steht unsere Fassung: `split_pinned` „teilt ein Objekt an einer
Ebene und setzt Passstifte in die Schnittfläche. Das Spiel kommt aus dem
Materialprofil." Und es funktioniert an jedem Objekt in der Szene, gleich
woher es kam.

**Der ehrliche Vergleich lautet also nicht „wir verstiften, sie nicht", sondern:**
Ihr Schnitt ist klüger, unsere Verbindung existiert. Wer eine erzeugte Figur
zerlegen will, ist bei ihnen besser bedient — solange sie aus ihrem eigenen
Haus stammt und keine Farben hat. Wer ein beliebiges Teil so trennen will, dass
es hinterher wieder zusammenfindet, hat dort kein Werkzeug.

Ein nicht-planarer Schnitt entlang der Form wäre für uns eine große, echte
Erweiterung — und der erste Punkt in diesem Dokument, an dem eine ihrer
Funktionen etwas kann, das wir nicht können und gebrauchen könnten (Befund B13).

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

### 3.7 Was auf der Gegenseite überhaupt nicht vorkommt

Für diesen Durchgang wurde das Register vollständig ausgelesen — alle 77
Operationen mit Titel und Beschreibung, nicht nur gezählt. Der Vergleich ist
danach schnell erzählt: **Fünf der fünfzehn Kategorien haben drüben kein
Gegenstück, nicht einmal ansatzweise.**

| Gruppe | bei uns | bei Meshy / Rodin |
|---|---|---|
| **Exakter Kern (B-Rep)** | `chamfer_edges`, `fillet_edges`, `draft_faces`, `shell_exact`, `thread_exact`, `push_face`, `create_brep_box`, `create_brep_cylinder`, `load_step` | nichts — Netze haben keine Kanten, an die eine Verrundung greifen könnte |
| **Skizze mit Zwängen** | `sketch_extrude`, `sketch_pocket`, `sketch_revolve`, `sketch_sweep`, `sketch_loft` | nichts |
| **Kalibrieren am eigenen Drucker** | `insert_fit_ladder`, `insert_wall_ladder`, `insert_overhang_fan`, `test_piece` | nichts — sie kennen den Drucker des Nutzers nicht |
| **Verbindungen und Normteile** | 18 Bausteine-Ops: Mutternfalle, Heat-Set-Buchse, Schraubenloch mit Senkung, Gewinde, Passstift, Rastnase, Filmscharnier, Schnappverbindung, Magnettasche, Kabeldurchführung mit Zugentlastung, Schlüsselloch, Wandhalter, Versteifungsrippe, Deckel, Drehdeckel | angekündigt als „KI-Steinteile-Generator", noch nicht ausgeliefert |
| **Druckvorbereitung mit Maß** | `hollow_object`, `compensate_first_layer`, `set_material`, `split_pinned`, `orient_for_print` | Auto Split und Reparatur, sonst nichts |

Die vier Kalibrierkörper verdienen einen eigenen Satz, weil sie das Prinzip in
Reinform zeigen: Die Toleranzleiter, die Wandstärkenleiter und der
Überhangfächer werden **einmal gedruckt**, ausgemessen, und der gemessene Wert
wandert ins Materialprofil. Danach rechnet jede Passung mit dem Spiel, das
*diese* Maschine mit *diesem* Filament tatsächlich hält. Ein Dienst in der
Cloud kann das grundsätzlich nicht — er weiß nicht, welcher Drucker im Keller
steht.

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

### 4.3 Der Akzent — warum das Fenster eintönig wirkt

Der Anlass für diesen Abschnitt war eine Beobachtung am laufenden Programm:
*Im Viewport und um die Panels ist nirgends ein oranger Akzent zu sehen.* Sie
stimmt, und der Grund ist im Code eindeutig belegbar.

**Die Farbe existiert und ist gut gewählt.** `theme.py:30` setzt
`_SELECTION = "#f0a54a"` — Bernstein, 69,2 % Sättigung, Kontrast **5,54**
gegen die Fensterfarbe. Sie ist in beiden Themen dieselbe und mit Bedacht
gewählt: derselbe Ton, in dem der Viewport einen gewählten Körper färbt, damit
Liste und Bild dieselbe Handlung gleich färben.

**Sie hängt an genau einer Sorte Zustand: dem flüchtigen.** Ausgelesen aus
`style.py`:

| Der Akzent erscheint bei | Regel |
|---|---|
| markierter Zeile in Baum, Liste, Tabelle | `::item:selected` |
| Primärknopf eines Dialogs | `QPushButton:default` |
| eingeschaltetem Werkzeug | `QToolButton:checked` |
| Tastaturfokus | `:focus` — 2 px Rahmen |
| Menüeintrag unter der Maus | `QMenu::item:selected` |
| laufendem Fortschritt | `QProgressBar::chunk` |

Alle sechs sind **Momentzustände**. Sie setzen voraus, dass gerade etwas
gewählt, gedrückt, überfahren oder berechnet wird. Im Handbuchbild des
Hauptfensters steht unten links „Keine Auswahl" — und deshalb ist auf dem
ganzen Bildschirm kein einziger Akzentpunkt. Genau das ist der Normalzustand
beim Hinsehen.

**Was der Akzent nicht tut: dauerhafte Struktur zeigen.** Ebenfalls aus
`style.py`:

- `QTabBar::tab:selected` bekommt `base` als Hintergrund und `line` als
  Rahmen — **kein Akzent**. Der aktive Reiter „Prüfbericht" unterscheidet sich
  vom inaktiven „Chat" also nur durch einen Flächenwechsel mit **1,10**
  Kontrast.
- `QHeaderView::section` — Fensterfarbe, gedämpfter Text.
- `QGroupBox::title` — gedämpft.
- `QSplitter::handle` — ein Pixel `line`.
- Die Panels selbst haben keine Kante zum Viewport.

**Und darunter liegt das eigentliche Problem: die Flächen sind zu eng
beieinander.** Nachgerechnet für das dunkle Thema:

| Flächenpaar | Kontrast |
|---|---|
| Panel gegen Fenster | **1,10** |
| Zebrazeile gegen Panel | **1,16** |
| Viewport-Verlauf unten gegen oben | **1,21** |
| Trennlinie gegen Fenster | **1,43** |

Sieben Rollen — Fenster, Panel, Zebrazeile, Trennlinie, Tooltip, beide
Viewport-Enden, Bettfläche — liegen sämtlich zwischen **1,3 % und 5,0 %
Helligkeit**. Ein Band von 3,7 Prozentpunkten für alles, was Fläche ist. Zum
Vergleich: Für Bedienelemente gilt 3,0 als Untergrenze der Erkennbarkeit; die
Trennlinie erreicht die Hälfte davon, und sie ist der **stärkste** Trenner im
Fenster.

Der Kommentar in `theme.py` hat die Richtung schon erkannt — die Trennlinie
stand vorher bei 1,05 und wurde ausdrücklich angehoben, weil „ein Knopf ohne
sichtbaren Rahmen kein Knopf ist, sondern Text". Der Schritt war richtig und
zu klein.

**Damit ist der Eindruck erklärt.** Es fehlt nicht an Farbe — es fehlt an
Hierarchie. Ein einziger, sehr kräftiger Ton (5,54) markiert Flüchtiges; alles
Bleibende teilt sich ein Helligkeitsband, in dem nichts vor oder zurücktritt.
Ein Fenster ohne Auswahl ist deshalb wörtlich einfarbig, und die Struktur —
was ist Panel, was ist Viewport, welcher Reiter gilt — muss der Betrachter aus
Linien erschließen, die selbst kaum zu sehen sind.

Der Vergleich mit den Generatoren ist an dieser Stelle ausnahmsweise unfair,
weil deren Bildschirme aus Inhalt bestehen: Eine Kachelwand aus texturierten
Figuren *ist* die Farbe. Der ehrliche Maßstab sind die Programme, aus denen
unsere Nutzer kommen — Fusion, OrcaSlicer, Bambu Studio. Alle drei arbeiten
mit deutlich abgestuften Flächen und einem Akzent, der den aktiven Bereich
markiert, nicht nur die Auswahl darin. Das ist keine Geschmacksfrage, sondern
Orientierung: Wer nicht sieht, wo er ist, sucht länger.

### 4.4 Was daraus folgt — ohne Regel 18 zu verletzen

Regel 18 verbietet Bedeutung **allein** über Farbe. Sie verbietet nicht, Farbe
als *zusätzliche* Kodierung für etwas zu benutzen, das ohnehin schon anders
erkennbar ist. Alle folgenden Punkte sind mehrfach kodiert und damit zulässig:

1. **Der aktive Reiter bekommt eine Akzentkante** (2 px oben oder unten). Er
   ist bereits durch Position und Flächenwechsel kodiert — die Kante macht ihn
   auf einen Blick auffindbar, statt auf den zweiten.
2. **Die Flächen weiter auseinanderziehen.** Panel gegen Fenster von 1,10 auf
   mindestens 1,5, die Trennlinie auf 3,0. Das ist reine Zahlenarbeit an
   `THEMES` und kostet keine Zeile Logik.
3. **Der Viewport bekommt Tiefe.** 1,21 zwischen unten und oben ist kein
   Verlauf, sondern eine Fläche mit Messfehler. Ein spürbarer Verlauf lässt
   den Körper vor dem Raum stehen, statt in ihm zu kleben.
4. **Der aktive Abschnitt links** (Objekte / Parameter / Verlauf) bekommt eine
   Akzentmarke am Kopf — zusätzlich zum Auf-/Zuklapp-Dreieck, das die
   Zweitkodierung schon liefert.
5. **Der geltende Schritt im Verlauf** wird markiert. Im Bild ist die Liste
   „Körper, Aushöhlen, Kabel und Befestigung, …" gleichförmig; wo der Stapel
   gerade steht, sagt sie nicht.

Was **nicht** passieren darf: Orange als Dekoration. Der Wert des Tons liegt
darin, dass er heute genau eine Bedeutung hat. Jede neue Verwendung muss eine
Frage beantworten, die der Nutzer wirklich stellt — *wo bin ich, was gilt
gerade, wo stehe ich im Ablauf* —, sonst verliert er seine Schärfe und das
Fenster wird bunt statt gegliedert.

### 4.5 Was wir nicht übernehmen

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
Handarbeit: gut geschrieben, aber jede einzeln zu pflegen, und der Umfang endet
bei den beworbenen Funktionen.

Dazu Bilder, wo ihr Quick Start keine hat, und zwei vollständige Sprachen.

**Wo ihre besser ist, und zwar deutlich: die Form.** Die Auto-Split-Seite hat
eine Kurzfassung, ein „Wann benutzen", ein **„Wann *nicht* benutzen"**, neun
nummerierte Schritte, Tipps zu geeigneten und ungeeigneten Modellen und vier
Fragen mit ehrlichen Antworten — einschließlich zweier Einschränkungen, die
das eigene Produkt schlecht aussehen lassen. Keine unserer zwanzig
geschriebenen Seiten hat diese Form. Der Abschnitt „Wann nicht" ist der,
den wir am dringendsten übernehmen sollten: Er erspart dem Leser den
Fehlversuch und wirkt vertrauenswürdiger als jede Werbezeile.

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

Zwei Zahlen im ganzen erzählenden Teil. Ihre *Dokumentation* nennt an dieser
Stelle ebenfalls keine Werte — aber sie ist nicht der Ort, an dem sie es
versuchen.

**Sie betreiben eine 3D-Druck-Akademie.** Fünf Module, 27 Lektionen, mit
Fortschrittszählern wie ein Kurs: Erste Schritte (5) — Druckerwahl, Sicherheit
bei Dämpfen und Feuer, Begriffe, Tag-1-Checkliste, Werkzeuge. Mit Meshy
erstellen (9). Materialien und Filamente (5) — warum mit PLA anfangen, wann auf
PETG wechseln, nasses Filament trocknen. Slicing und Software (6) — wie Slicing
funktioniert, Profil abstimmen, Stützstrukturen, Mehrfarbe. Fehlersuche (2) —
ungleichmäßige erste Schicht, zu dünn gedruckte Details. Die Lektionstexte
selbst waren ohne Konto **nicht einsehbar**; ob dort Zahlenwerte stehen, ist
nicht geprüft.

Das ist inhaltlich genau der Stoff, der unserem Handbuch fehlt. Der Befund aus
der ersten Fassung — „wir haben die Werte und sie nicht" — war zu bequem. Er
lautet richtig:

> **Ihr Fertigungswissen ist Lesestoff neben dem Werkzeug. Unseres ist im
> Werkzeug — es rechnet, prüft und warnt. Nur lesen kann man es nicht.**

Im Programm liegen:

- **6 Materialprofile** (PLA, PETG, PETG-CF, ASA, ABS, TPU-95A) mit `clearance`,
  `press`, `shrinkage`, `elephant_foot`, `hole_compensation`, `calibrated`
- **16 Druckerprofile** ab Werk (Bambu A1/A1 mini/P1S/X1C, Creality Ender-3 V3
  und K1, Anycubic Kobra 2, Elegoo …)
- **40 Normteilmaße** in acht Tabellen (`standards.toml`): 7 Schrauben,
  7 Muttern, 4 Scheiben, 6 Einpressbuchsen, 5 Magnete, 4 Lager, 3 Profile,
  4 Rohre
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
Technik wie die Op-Referenz) und veralten nie (Befund B4). Der Unterschied zu
einer Akademie ist dabei der Punkt, nicht der Mangel: Eine Lektion sagt, was
man tun sollte; eine erzeugte Seite sagt, **wonach das Programm gerade
gerechnet hat**, mit dem Wert, der im Prüfbericht steht. Der Bauplan nennt die
Regelsammlung in §39 „das eigentliche Produkt". Ein Produkt, das man nicht
lesen kann, ist schwer zu verkaufen.

---

### 5.3 Was neben dem Handbuch steht — und uns direkt betrifft

Meshy betreibt eine Strecke kostenloser Browser-Werkzeuge **ohne Konto**. Fünf
sind ausgeliefert: STL-Reparatur, Dateikonverter, Online-Betrachter,
Dateikompressor, 3D-Textgenerator. Acht weitere stehen als graue Kacheln
daneben, ausdrücklich als Fahrplan gekennzeichnet — darunter ein
„KI-Steinteile-Generator" für Scharniere, Träger und Zahnräder mit
druckfertigem STL. Das wäre eine Überschneidung mit unserer
Bausteinbibliothek; heute ist es eine Ankündigung.

**Die STL-Reparatur ist der Punkt, der uns betrifft.** Sie behebt
nicht-mannigfaltige Kanten, Löcher und umgedrehte Normalen, baut eine
wasserdichte Topologie, nimmt STL, OBJ und GLB bis 100 MB, braucht etwa eine
Minute — und kostet nichts. Das ist Funktion für Funktion unsere Op `repair`.

Daraus folgt eine Anpassung der eigenen Erzählung: **Die Reparatur allein ist
kein Verkaufsargument mehr.** Sie ist im Netz gratis und ohne Anmeldung zu
haben. Was bleibt, ist alles, was danach kommt — Maß, Passung, Schichtanalyse,
Stapel. Wo unsere Website heute „einlesen, reparieren, aufs Bett setzen"
sagt, muss die Betonung auf dem stehen, was ein Reparaturknopf nicht kann.

**Und ein Muster lohnt die Nachahmung.** Auf ihrer Reparaturseite steht eine
Tabelle, die vier Wege gegeneinanderstellt — manuelle Reparatur in Blender,
gekaufte Reparatursoftware wie Netfabb oder Magics, ein Druckservice, und ihr
Werkzeug — mit sechs Zeilen und einer ehrlichen Fußnote, dass die Spalten
typische Vertreter beschreiben. Genau diese Form empfiehlt Befund B1 für uns.
Es ist die wirksamste Seite ihres ganzen Auftritts, und sie besteht aus einer
Tabelle.

Dazu kommt eine Maschine, die wir nicht haben und nicht bauen werden:
Vergleichsseiten gegen jeden namhaften Wettbewerber („Meshy vs. Tripo",
„vs. Trellis 2", „vs. Hunyuan3D"), ein Glossar, die Akademie, ein Blog mit
datierten Fachartikeln, Discord, YouTube, TikTok, LinkedIn. Das ist Marktarbeit
im industriellen Maßstab. Der einzige sinnvolle Schluss daraus ist **nicht**,
es nachzubauen, sondern die zwei Seiten zu haben, die ein Suchender bei uns
finden muss: den Vergleich (B1) und die Kette vom erzeugten Modell zum Druck
(B3).

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
| **Konstruieren mit Maß** | **konkurrenzlos** — exakter Kern, Skizze mit Zwängen, Kalibrierkörper, 18 Verbindungsbausteine; fünf ganze Kategorien ohne Gegenstück (3.7) |
| **Mehrfarbe und Aufbereitung generierter Netze** | **überlegen** — Kette gemessen, lokal, wiederholbar, ohne Guthaben; ihre geteilten Teile verlieren die Farbe sogar |
| **Teilen** | **geteiltes Urteil** — ihr Schnitt folgt der Form (können wir nicht), unsere Verstiftung existiert (haben sie nicht, und verweisen dafür auf Blender) |
| **Reparieren** | **gleichauf** — ihre kostenlose STL-Reparatur deckt unsere `repair`-Op ab |
| **Handbuch** | **überlegen** in der Referenz, **unterlegen** in Form und Lernstoff (27 Akademielektionen gegen null) |
| **Erzeugen aus Text und Bild** | **chancenlos** — und nach §42 nicht unser Rennen |
| **Reichweite, Ökosystem, Integrationen** | **chancenlos** — 12 Mio. Nutzer gegen einen Einzelentwickler vor Version 1.0 |
| **Preis und Eigentum** | **überlegen**, wird nicht ausgespielt |
| **Erster optischer Eindruck** | **unterlegen** im Hauptfenster, **gleichauf** bei Startbildschirm und Katalog |
| **Gliederung der Oberfläche** | **eigenständige Schwäche** — sieben Flächenrollen in einem Helligkeitsband von 3,7 Punkten, der Akzent nur auf Flüchtigem (4.3, B16) |

Der Satz, der aus den ersten drei Zeilen folgt:
*Meshy erzeugt Dinge, die aussehen wie etwas. Solidon macht Teile, die passen —
auch die, die Meshy erzeugt hat.*

---

## Teil 8 — Was die späteren Durchgänge korrigiert haben

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

### Der dritte Durchgang, nach der Frage „hast du wirklich alles angesehen?"

Die Antwort war nein. Die zweite Fassung hatte von der Meshy-Webapp-Doku nur
die Navigationsliste gesehen, keine einzige Seite; zwei geratene Pfade gaben
404, danach blieb es bei `llms-full.txt`. Was daraus folgte, war falsch:

5. **„Auto Split kommt in ihrer Dokumentation nicht vor — beworben, nicht
   dokumentiert."** Falsch, und es war sogar als Argument benutzt worden. Die
   Seite existiert unter `/en/webapp/guides/3d-model/auto-split`, ist
   ausführlich und ehrlicher als unsere eigenen: mit „Wann *nicht* benutzen"
   und zwei Einschränkungen, die das eigene Produkt schlecht aussehen lassen.
   Das „nicht gefunden" war ein Abschneide-Artefakt der Volltextdatei — ein
   Werkzeugfehler, den ich als Befund ausgegeben hatte. Der richtige Vergleich
   steht jetzt in 3.2 und fällt an einer Stelle **gegen** uns aus: Ihr Schnitt
   folgt der Form, unserer einer Ebene.
6. **„Wir haben die Werte, sie nicht."** Zu bequem. Sie betreiben eine
   3D-Druck-Akademie mit 27 Lektionen. Der Unterschied ist nicht Besitz,
   sondern Wirksamkeit (5.2).
7. **Die kostenlose Werkzeugstrecke war übersehen worden** — darunter eine
   STL-Reparatur, die unsere `repair`-Op eins zu eins abdeckt, gratis und ohne
   Konto (5.3).

Methodisch bleibt daraus eine Regel für den nächsten Durchgang: **Eine
Zusammenfassung, die etwas *nicht* findet, ist kein Beleg dafür, dass es
fehlt.** Negative Befunde brauchen die Seite selbst, im Browser, mit der
Navigation der Gegenseite statt geratener Pfade.

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

### B16 — Flächen abstufen und den Akzent an Bleibendes binden · **hoch** · klein bis mittel

Der Befund aus 4.3, in Zahlen: Panel gegen Fenster 1,10 · Zebrazeile gegen
Panel 1,16 · Viewport-Verlauf 1,21 · Trennlinie gegen Fenster 1,43. Sieben
Flächenrollen zwischen 1,3 % und 5,0 % Helligkeit. Der Akzent hat 5,54
Kontrast und erscheint ausschließlich bei Auswahl, Fokus, Hover, gedrücktem
Knopf und laufendem Fortschritt — also nie im Ruhezustand.

Zwei Teile, verschieden teuer:

**Teil A, reine Zahlenarbeit an `THEMES` (klein).** Panel gegen Fenster auf
mindestens 1,5, Trennlinie auf 3,0, Viewport-Verlauf spürbar. Kein
Logikeingriff, keine neue Regel — aber sämtliche Bildschirmfotos des Handbuchs
müssen danach neu aufgenommen werden (`tools/make_figures.py`, **nicht**
offscreen, sonst fehlen die Schriften), und `tests/test_theme_and_palette.py` prüft
die Kontraste mit.

**Teil B, der Akzent an fünf bleibende Zustände (mittel).** Aktiver Reiter,
aktiver Abschnitt links, geltender Schritt im Verlauf — jeweils *zusätzlich*
zu einer bestehenden Kodierung, damit Regel 18 unberührt bleibt. Die Liste
steht in 4.4.

Priorität hoch, weil es den ersten Eindruck betrifft und weil Teil A billiger
ist als jede andere Maßnahme in diesem Dokument. Vor der Umsetzung gehört ein
Blick auf Fusion und OrcaSlicer im Vollbild daneben — nicht auf die
Generatoren, deren Bildschirme aus Inhalt bestehen.

### B8 — Vorschaubilder im Objektbaum · **niedrig** · mittel

Die Renderstrecke existiert und wird im Bausteinkatalog benutzt. Sie auf
Szenenobjekte anzuwenden ist Fleißarbeit mit sichtbarer Wirkung.

### B9 — Kennzahlenkopf über dem Prüfbericht · **niedrig** · klein

Wasserdicht, Volumen, Komponenten, schmalste Wand, schlimmster Überhang — als
schmale Zeile über der Befundliste. Die Werte liegen alle vor. Ihre Darstellung
ist an dieser einen Stelle besser als unsere, und der Grund ist kein
technischer.

### B10 — Rodins ControlNet · **beantwortet: nein** · 12.08.2026

Erzeugung, die in einen vorgegebenen Hüllquader hineinrechnet, ist die einzige
Idee der Gegenseite, die unser Kernproblem berührt: generierte Netze haben
keine Maße.

**Unser Weg kann es nicht.** Nachgesehen in den mitgelieferten Workflows
(`app/core/backends/data/`): `Hy3DMeshGenerator` nimmt `model`, `image`,
`steps`, `guidance_scale`, `seed`, `attention_mode` — und sonst nichts. Kein
Hüllquader, keine Voxel, keine Punktwolke. Das liegt nicht am Workflow, sondern
am Modell: Formvorgabe ist ein Merkmal von Rodins Gen-2.5, nicht der
Knotensammlung Hunyuan3D 2.1. Ein anderes Modell könnte es mitbringen, und der
Workflow ist eine Datendatei — das ist der Grund, warum §27 ihn als Datei führt
und nicht als Code.

**Was wir stattdessen haben, ist die Gegenrichtung.** Rodin gibt die Form
vorher vor; wir bringen sie hinterher auf Maß — `fit_to_size` skaliert auf eine
Kantenlänge, `check_build_volume` sagt, ob es auf die Platte passt. Das ersetzt
keine Proportionsvorgabe, beantwortet aber die Frage, die ein Drucker stellt.

### B13 — Nicht-planarer Schnitt · **offen, weil noch nicht gebaut** · groß

*Dieser Befund steht in diesem Dokument zweimal: hier die geprüfte Fassung, und
unten die ursprüngliche samt Nachtrag vom 13.08.2026, der die halbe Begründung
zurücknimmt. Der Status hier ist der geltende.* **Beantwortet ist die Frage
nach dem Weg, gebaut ist nichts** — nachgesehen am 14.08.2026: `autosplit.py`
holt seine Normale weiter aus `AXIS_NORMALS`, die Suche kennt also drei Achsen.

Der einzige Punkt im ganzen Vergleich, an dem eine ihrer Funktionen etwas kann,
das wir nicht können und gebrauchen könnten.

**Der naheliegende Weg ist geprüft und verworfen — vor diesem Konzept.** Der
Modulkopf von `geom/autosplit.py` sagt, dass bei erfolgloser Ebenensuche die
konvexe Zerlegung gefragt wird, wo ein Körper von selbst auseinanderfällt, und
der Schnitt dorthin gelegt wird: *„als Ebene, nicht als die Hüllen selbst.
Hüllenstücke sind eine Näherung, und eine Näherung wieder zusammenzukleben
ergibt ein genähertes Teil (§11.1)."* Ein Schnitt entlang V-HACD-Hüllen ist
also kein offener Weg, sondern ein bewusst geschlossener.

**Was offen bleibt und regelkonform wäre: die geneigte Ebene.** `SectionPlane`
trägt bereits eine freie Normale (`normal: Vec3`) — nur die *Suche* kennt drei
Achsen (`AXIS_NORMALS`, `_axis_to_cut`). Eine Ebene, die einer schrägen Kante
folgt, versteckt ihre Naht dort, wo ohnehin eine Kante läuft, bleibt exakt
statt genähert und behält die Verstiftung, die heute funktioniert. Das ist
nicht Meshys formfolgender Schnitt, aber es ist der Teil davon, der ohne ein
trainiertes Segmentierungsmodell zu haben ist.

Der Kundenkreis entscheidet, ob es sich lohnt: Wer Halterungen und Gehäuse
druckt, teilt an einer Ebene und verstiftet. Wer Figuren druckt, will die
versteckte Naht — und ist heute nicht unser Kunde.

### B11 — Qualitätsstufe als Angebot statt als Einstellung · **niedrig** · klein

`ctx.quality` gibt es. Wo eine lange Rechnung beginnt, könnte die Wahl mit
einer Zeitschätzung stehen — Wartezeitverhalten nach §2.8, als Angebot
formuliert statt als Voreinstellung.

### B12 — Leerraum im Operationsdialog prüfen · **niedrig** · klein

Rund 90 Pixel über dem Beschreibungssatz. Entweder gehört dort eine Vorschau
hin, oder der Dialog ist zu hoch. Eine Messung am laufenden Fenster
entscheidet das in fünf Minuten.

### B13 — Nicht-planarer Schnitt · **offen** · groß · *ursprüngliche Fassung*

*Die geprüfte Fassung dieses Befundes steht weiter oben; hier bleibt der
Wortlaut von damals stehen, weil der Nachtrag am Ende sich darauf bezieht.*

Der einzige Punkt im ganzen Vergleich, an dem eine ihrer Funktionen etwas kann,
das wir nicht können und gebrauchen könnten. `split_plane` und `split_pinned`
schneiden an einer Ebene; ihr Verfahren folgt der Form, und die Naht versteckt
sich in der Struktur. Für Figuren und organische Teile ist das sichtbar besser.

Vor jeder Umsetzung gehört die Frage geklärt, ob es zum Kundenkreis passt: Wer
Halterungen und Gehäuse druckt, teilt an einer Ebene und verstiftet. Wer
Figuren druckt, will die versteckte Naht. Der zweite ist heute nicht unser
Kundenkreis — und der Ausbau würde nur mit Verstiftung entlang einer krummen
Fläche Sinn ergeben, was die Sache erheblich vergrößert.

> **Nachtrag 13.08.2026 — die halbe Begründung ist entfallen.** Mit der
> Entscheidung zu P16 (`konzept-organische-modellierung-2026-08.md` §17) gehören
> Figuren zum Kundenkreis. Der Satz „der zweite ist heute nicht unser
> Kundenkreis" gilt nicht mehr und trägt hier nichts mehr.
>
> Was **weiter** gilt, ist die technische Hälfte: Ein Schnitt entlang
> V-HACD-Hüllen bleibt abgelehnt (`geom/autosplit.py`, §11.1 — eine Näherung
> wieder zusammenzukleben ergibt ein genähertes Teil), und die Verstiftung
> entlang einer krummen Fläche bleibt der teure Teil. Der offene Weg ist
> weiterhin die **geneigte Ebene**: `SectionPlane` trägt schon eine freie
> Normale, nur die Suche kennt drei Achsen.
>
> Damit wird B13 von „abgelehnt, weil Kundenkreis" zu „offen, weil noch nicht
> gebaut" — neu zu bewerten nach P16, nicht darin.

### B14 — „Wann nicht benutzen" in die Handbuchseiten · **mittel** · klein

Ihre Auto-Split-Seite nennt fünf Fälle, in denen man das Werkzeug **nicht**
nehmen soll, und zwei Einschränkungen, die das eigene Produkt schlecht
aussehen lassen. Das wirkt vertrauenswürdiger als jede Werbezeile und erspart
den Fehlversuch. Bei Operationen mit Grenzen — `split_pinned`, `hollow_object`,
`decimate_mesh`, `create_from_scad`, `lattice_fill` — gehört derselbe Abschnitt
ins Handbuch. Er lässt sich nicht erzeugen; er muss geschrieben werden.

### B15 — Die Erzählung um die Reparatur korrigieren · **mittel** · klein

Meshys STL-Reparatur ist gratis, ohne Konto, nimmt STL/OBJ/GLB bis 100 MB und
deckt unsere `repair`-Op eins zu eins ab. Reparieren allein trägt kein
Verkaufsargument mehr. Auf Website und in Weg 1 muss die Betonung dorthin
wandern, wo ein Reparaturknopf endet: Maß, Passung, Schichtanalyse, Stapel.

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

*Stand 12.08.2026, vierte Fassung. Der eigene Stand ist aus dem laufenden Code
gemessen — alle 77 Operationen, alle 16 Bausteine, alle Wissenstabellen, die
Farbkette eigens durchgefahren, Themenfarben auf Kontrast und Sättigung
nachgerechnet, alle sechs Bildschirmfotos angesehen. Der
Marktstand stammt von den Seiten der Anbieter, im dritten Durchgang über ihre
eigene Navigation im Browser abgerufen. Preise, Nutzerzahlen und
Aufbewahrungsfristen sind ihre Angaben, keine geprüften Werte. Nicht einsehbar
und deshalb nicht bewertet: die Lektionstexte ihrer Akademie und die
Webanwendung selbst — beides liegt hinter einem Konto.*

---

## Teil 10 — Was daraus wurde (12.08.2026)

Abgearbeitet, jeder Punkt mit Test und eigenem Commit. Die Zeilen sind der
Stand, nicht die Absicht.

| Befund | Stand |
|---|---|
| **B1** Vergleichstabelle Druckbarkeit | Website, beide Sprachen, mit Datum und Quelle |
| **B2** Analysekarten nach vorn | **teilweise** — der Text argumentiert damit, das Bild fehlt |
| **B3** Kette für generierte Netze | Website-Abschnitt „Wenn das Modell aus einer KI kommt", fünf Schritte |
| **B4** Fertigungswissen ins Handbuch | zwei erzeugte Seiten; Regelsammlung dafür zweisprachig |
| **B5** Handbuchform | 20 Kurzfassungen, erzeugte Meldungstabelle im Wortlaut |
| **B6** Referenz der Fernsteuerung | erzeugt; zehn Werkzeuge waren gar keine Operationen und fehlten |
| **B7** Preisrechnung | 240–360 $/Jahr gegen 49 € einmal, beide Sprachen |
| **B8** Vorschaubilder im Objektbaum | gerendert, nach Objekt-Hash gecacht, eines je Ereignisschleife |
| **B9** Kennzahlenkopf im Prüfbericht | wasserdicht · Volumen · Teile |
| **B10** Rodins ControlNet | **beantwortet: nein** — Hunyuan3D 2.1 hat keine Formvorgabe |
| **B11** Qualitätsstufe als Angebot | als Restzeitschätzung umgesetzt; der Umschalter wäre eine Betriebsart gewesen |
| **B12** Leerraum im Operationsdialog | 189 → 26 px; es war eine fehlende Größenrichtlinie |
| **B13** Nicht-planarer Schnitt | **offen** — der Weg ist beantwortet (geneigte Ebene statt Hüllen), gebaut ist nichts: die Suche kennt weiter drei Achsen. Diese Zeile stand bis zum 14.08.2026 auf „beantwortet" und widersprach damit dem Nachtrag über ihr |
| **B14** „Wann nicht benutzen" | fünf Operationen mit echter Grenze |
| **B15** Erzählung um die Reparatur | Website: reparieren allein trägt kein Argument mehr |
| **B16** Flächen abstufen, Akzent binden | Kontraste 1,10 → 1,45, Trennlinie 1,43 → 2,30, Reiterkante |

**Was dabei über den Auftrag hinausging**, weil es sich beim Bauen zeigte: Die
Karten tragen ihre Kante im Akzent — gegen die Warnung dieses Konzepts, auf
ausdrückliche Entscheidung, und der Grund steht im Bild. Der Zeiger im Viewport
sagt, was ein Klick täte, und gilt auch in den Panels.

**Was offen bleibt.** B2 braucht ein Bildschirmfoto einer Analysekarte, das der
Abbildungskatalog nicht hat. Die Website läuft mit 1456 px in einem Fenster von
1265 px über — der Überlauf steht schon vor diesen Änderungen im HEAD, kein
Element ragt über den Rand. Und in der Statuszeile überlappen sich „Keine
Auswahl" und der Demo-Hinweis; beides gehört nicht zu diesen Befunden.

---

## Nachrecherchiert am 19.08.2026

Fünfundvierzig Einzelaussagen über den eigenen Stand geprüft: **17 stimmen, 23
sind überholt, 4 sind falsch, eine ist nicht prüfbar.** Dazwischen liegen P16,
der Sprung von zwei auf sechs Sprachen und die Durchsicht vom 14.08.

**Zwei Zahlen waren falsch, nicht überholt:**

- Der Kontrast des Bernstein-Akzents gegen die Fensterfarbe beträgt **5,54**,
  nicht 7,27. Der Kommentar in `theme.py:38` sagt es selbst („Gegen das dunkle
  Fenster bringt er 5,4"). 7,93 ist der Kontrast von Bernstein gegen die
  *Schrift darauf* — vermutlich die verwechselte Zahl. Beide Farben stehen
  unverändert seit vor dem 12.08.; die Zahl war also schon damals falsch.
- **`tests/test_accessibility.py` hat nie existiert.** Die Kontraste prüft
  `tests/test_theme_and_palette.py`.

**Was die Zeit überholt hat:** 77 Operationen → 85, zwei Sprachen → sechs, und
sämtliche Zeilennummern.

**Die Außenrecherche trifft den Kern dieses Dokuments** — die Frage lautete, ob
wir mithalten:

- **Meshy 7 ging am 10.08.2026 live**, zwei Tage vor diesem Papier: ein
  Bild-zu-3D-Grundlagenmodell, das auf die Ausrichtung zwischen Eingabebild und
  Ergebnis zielt.
- **Die Druckbarkeitsprüfung kostet bei Meshy nichts.** „Analyze Printability"
  ist als API-Aufruf kostenlos und meldet Wasserdichtheit, nicht-mannigfaltige
  Kanten, Löcher als Randschleifen und entartete Flächen — dieselbe Liste, die
  Solidons Prüfbericht führt. Die Reparatur kostet 10 Guthaben, der
  Mehrfarbdruck 10.
- **Das Kreativlabor rechnet in Millimetern.** Die Endpunkte erschienen am
  01.06.2026; der Schlüsselanhänger nimmt die Kantenlänge des umschließenden
  Quadrats in Millimetern (0 bis 400). Das ist die Richtung, aus der ein
  Generator in unser Feld kommt: nicht über bessere Netze, sondern über echte
  Maße an fertigen Produkten.
- **Seit dem 08.04.2026 gibt es eine Formlabs-Anbindung** — „Print with Form
  Now" schickt ein Modell direkt in den Fertigungsdienst.
- **Bei Hyper3D Rodin ist die API-Schranke höher, als hier steht:** Zugang erst
  ab Business (120 $/Monat), Free und Creator haben keinen.

**Nicht belegbar und deshalb offen gelassen:** die Nutzer- und Modellzahlen, die
Meshy über sich selbst angibt (100 Mio. Modelle, 12 Mio. Nutzer). Sie stehen im
Dokument als Selbstauskunft und bleiben es.

**Was sich am Urteil nicht ändert:** Rodin bleibt der ungefährlichere. Meshy
steht weiter auf unserem Feld — und ist ihm seit dem 12.08. einen Schritt näher
gekommen, nicht ferner.
