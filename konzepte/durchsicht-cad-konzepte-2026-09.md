# Durchsicht der CAD-Konzepte — 19.09.2026

> **Gegenstand:** [konzept-vollwertiges-cad-2026-09.md](konzept-vollwertiges-cad-2026-09.md),
> [recherche-cad-paritaet-2026-09.md](recherche-cad-paritaet-2026-09.md) und
> [konzept-bedienung.md](konzept-bedienung.md). Geprüft am Stand `87273de06`
> mit den ungestagten Änderungen einer parallelen Sitzung im Baum (Formschräge,
> Bett-Bindung, Auswahlkarte — keine davon berührt die geprüften Stellen).
> Python 3.14.7, lokale `.venv`, Windows. **Anwendungscode unverändert.**
>
> **Ergebnis in einem Satz:** Die Messungen der beiden CAD-Dokumente halten
> am heutigen Stand bis auf die vierte Stelle; korrigiert werden eine Zählung,
> ein Plattformbefund, drei Formulierungen und der Registerstand des
> Bedienprotokolls — und zwei der gemessenen Lücken sind Kundenfehler von
> heute, die nicht bis nach 0.4.3 warten sollten.
>
> Sonden und Protokolle: `.claude/.state/cad-durchsicht-2026-09-19/`.
>
> **Entscheidung Robert, 19.09.2026, nach dieser Durchsicht:** 0.4.3 ist
> draußen (Tag `v0.4.3` vom 18.09., `version.json` auf dem Server); die
> parallel laufenden Codeänderungen werden als 0.4.4 veröffentlicht, danach
> startet der Plan und wird abgearbeitet, bevor die darauffolgende Version
> hochgeladen wird. Alle Empfehlungen aus §7 sind in das Konzept eingearbeitet
> (§14.3: P0.0, P0.7, P1.6, P4.0, Reihenfolge §13.10); die Korrekturen aus
> §3 stehen an ihren Stellen. Dieses Dokument bleibt als Beleg.

---

## 1. Was nachgemessen wurde

Acht Sonden über den Kern, ohne Fenster. Jede wiederholt eine Messung aus dem
Konzept oder der Recherche mit den dort genannten Eingaben.

| Behauptung (Quelle) | Befund heute | Sonde |
|---|---|---|
| 132 Ops in 15 Kategorien, alle rücknehmbar; 35 Bausteine; 12 Merkmalsarten; 15 Bedingungen (Konzept §2) | **stimmt** | `s1_register.py` |
| Exakte Spiegelung: 6 Merkmale vor, 0 nach, kein Befund (Konzept §3 B, Recherche §2.2) | **stimmt** — `kind="brep"` bleibt, `features` leer, Prüfbericht ohne Zeile | `s2_mirror_scale.py` |
| Gleichförmig skalieren: 12 statt 6 Flächen, alte Inhalte 300/400/1200 mm² an verschobenen Mittelpunkten, auf **beiden** Kernen (Recherche §2.2) | **stimmt** | `s2_mirror_scale.py` |
| Ungleichförmig (X × 2): 10 Flächen (Recherche §2.2) | **stimmt** — 4 alte, 6 neue, auf beiden Kernen | `s8_matrix.py` |
| NURBS-Körper: `features_of` leer, auch nach STEP-Rundreise; OCCT erkennt 6 Ebenen und Ø6 (Recherche §§2.1, 5.2) | **stimmt** — Ø 5,999999999999634 mm, größter Gap 3,5·10⁻¹³ | `s3_nurbs.py` |
| Torus: `features_of` leer; `GeomConvert_SurfToAnaSurf` liefert R 15 / r 3 (Recherche §5.2) | **stimmt** — auch am **analytischen** OCCT-Torus liefert `features_of` nichts | `s3_nurbs.py` |
| Radiusreihe: Schwerpunktfit misst zu klein, Formel `d·√(5+4cos(2π/n))/3` (Konzept §4) | **stimmt auf vier Stellen**, alle neun Zeilen; 8- und 12-Eck keine Bohrung | `s4_radius.py` |
| Ø0,5-Bohrung unerkannt: 52 Kantenkandidaten, zwei Kreisfacetten als Bezug, Abstand 0,173891 mm (Recherche §4.4) | **stimmt** — `edge_33`/`edge_34`, 0,17389 mm | `s5_placement.py` |
| Projizieren: sechs von sechs Flächen von `plate_holes.stl` scheitern; 1e-3 ins Material liefert 392 Strecken (Konzept §6) | **stimmt** | `s6_project.py` |
| `edge_key`: nach Verschiebung um (1, 2, 3) mm kein gemeinsamer Schlüssel (Konzept §13.3) | **stimmt** — 12 vor, 12 nach, 0 gemeinsam | `s7_edgekey.py` |
| Sechs-Schritte-Kundenweg kippt bei *Einpressbuchse*, Schwere `info` (Konzept §5.1) | **stimmt** — Verrunden 11 Merkmale exakt, Aushöhlen 22 exakt, Buchse Netz mit `info`, Senken Netz mit `info` | `s8_matrix.py` |

Dazu 31 statische Behauptungen über Dateien, Zeilen und Vorgaben, gelesen am
Arbeitsbaum: **28 stimmen**, drei weichen ab (§3.1, §3.4, §5).

Und die Bibliotheks-, Versions- und Lizenzangaben der Recherche gegen die
Primärquellen: **alle elf PyPI-Versionen sind aktuell**, alle
Lizenzangaben stimmen, OCCT 8.0.1 ist das aktuelle Release, pybind11
unterstützt 3.14 seit 3.0.0. **Eine Korrektur:** Open3D 0.20.0 hat auf PyPI
keine Intel-macOS-Wheels, für keine Python-Version (§3.2).

---

## 2. Die Matrix, die das Konzept sich selbst schuldig war

Konzept §5 nennt seine 20/3/56-Zählung eine Stichprobe und verlangt für die
Umsetzung „eine vollständige Matrix je Eingabeart". Die Sonde `s8_matrix.py`
fährt sie für den B-Rep-Eingang: je Operation ein frisches Dokument mit
exaktem Quader 40 × 30 × 10 und exakter Bohrung Ø5, dann die Operation mit
ihren Vorgaben, `at_feature` auf die Bohrung beziehungsweise eine Fläche.

| Ausgang | Ops | Was dahintersteht |
|---|---:|---|
| Netz | **57** | 31 Bausteine · 8 `mesh` (mit `brep_to_mesh`) · 7 `holes` · 3 `colour` · 3 `prepare` · 2 `transform` · `repair` · `bead_edges` · `apply_texture` |
| exakt | **19** | die 15 geometrischen aus der Konzeptliste plus `shell_exact`, `arrange_bed`, `check_collisions`, `orient_for_print` |
| angehalten | 21 | Pflichtparameter fehlte oder Geometrie nicht anwendbar (Deckel auf massivem Körper, Ebene schneidet nichts, Dichtung ohne Profil); für die Bauartfrage ohne Aussage |
| erzeugt | 27 | Erzeuger ohne Eingang |
| zwei Eingänge | 6 | die vier Booleschen, `replace_profile_liners`, `check_join_path` — nicht gefahren |
| Grundlage | 2 | `create_brep_box`, `drill_brep_hole` |

Gegenüber dem Konzept ändern sich zwei Zahlen und eine Aussage:

- **57 statt 56.** `clear_filament` fehlt in der Konzeptliste; die Kategorie
  `colour` hat drei konvertierende Ops, nicht zwei.
- **Die „20" enthalten fünf, die keine Geometrie liefern** (`delete_object`,
  `set_material`, `check_join_path` und die drei Booleschen mit zwei
  Eingängen), und ihnen fehlen drei Szenenoperationen, die den exakten Körper
  tatsächlich erhalten. Für die Paritätsabnahme zählt die Matrix, nicht die
  Liste.
- **`slots_from_texture` „bleibt exakt" ist ein Zufall.** Die Op ruft
  `as_mesh_data` und tesselliert; sie gibt den Eingang nur zurück, weil ein
  Solid keine Textur trägt (`geom/texture.py:229–231`). Mit Textur wäre auch
  sie ein Netz.

---

## 3. Korrekturen an den beiden CAD-Dokumenten

### 3.1 Zählungen und Formulierungen

| Stelle | Steht dort | Richtig ist |
|---|---|---|
| Konzept §3 A, §5 | 56 Ops machen ein Netz, `colour` 2 | 57, `colour` 3 (§2) |
| Konzept §2 | „AGENTS.md nennt noch 27 — veraltet" | Der Satz in AGENTS.md beschreibt den am 03.09. gefallenen Test und die Zahl von damals; er ist historisch, nicht falsch. **Veraltet ist** der Docstring in `app/ui/panels.py:907` („siebenundzwanzig") |
| Konzept §6.1 | „`up_to`/`height_to` gibt es nur für `sketch_extrude`" | `up_to` ist der Parameter; `height_to` ist die Funktion in `sketch/planes.py`, die ihn auflöst. Sinngemäß richtig, als Parameterpaar falsch |
| Konzept §5, Recherche §1 | `slots_from_texture` bleibt exakt | tesselliert ebenfalls; erhält den Solid nur ohne Textur (§2) |
| Recherche §5.1 | „Lokal lief Python 3.14.2" | Auf dieser Maschine läuft die `.venv` mit 3.14.7 wie `constraints.txt`. Die Angabe stammt von einer der beiden anderen Maschinen und gehört als solche gekennzeichnet |
| Konzept Kopf | Prüfstand `2148ddfa`, Abgleich `6ea0575e` | fünf Commits weiter (`87273de06`) gelten alle Kernbefunde unverändert (§1) |

### 3.2 Open3D und das Hardware-Fenster

Der Dateibefund vom 19.09. bleibt bestehen: Für 0.20.0 gibt es auf PyPI
ausschließlich `macosx_11_0_arm64`-Räder, für jede dort gelistete
Python-Version. Die Linux-Räder tragen `manylinux_2_35`, also glibc ≥ 2.35.
Mit dem Hardware-Fenster von acht Jahren gehören Intel-Macs bis 2020 zum
Kundenkreis. Der damalige Schluss „für den macOS-Weg keine Option“ ging
jedoch weiter als dieser Paketbefund.

**Präzisierung am 20.09.:** Open3D wird derzeit nicht aufgenommen, weil der
fertige Intel-Paketweg und ein Korpusvorteil fehlen. Der offizielle
macOS-Quellbau ist dokumentiert; ein Intel-/Python-3.14-Eigenbau ist hier
weder nachgewiesen noch als unmöglich widerlegt. Lizenz, Paketweg und
fachliche Eignung werden getrennt bewertet. Die jetzige Entscheidung steht
im Konzept §13.8.1. [Paketdateien](https://pypi.org/project/open3d/0.20.0/#files),
[Quellbau](https://www.open3d.org/docs/latest/compilation.html).

### 3.3 Analysis Situs ist eine Portierung, keine Bibliothek

Beide Dokumente führen Analysis Situs als „Reserve für Restlücken". Die
Primärquellen zeigen, was das kosten würde: keine Python-Bindings (Skripting
nur Tcl), Active Data ist kein externes Paket, sondern als `src/asiActiveData`
eingebettet und Basis des Datenmodells, gebaut gegen OCCT 7.6 bei unseren
8.0.1. Die kanonische Erkennung arbeitet auf B-Rep, nicht auf Netzen. Die
„Reserve" wäre also eine Quelltextportierung einzelner Algorithmen gegen eine
andere OCCT-Version — das darf die Bibliothekstabelle so nennen, damit
niemand sie für einen `pip install` hält.

### 3.4 Drei statische Abweichungen

- **`place_on_bed` beim Import** (Konzept-Bedienung „Teilweise"): Die Vorgabe
  ist weiterhin `False`, aber `ingest/plan.py:246` setzt für das erste Modell
  `{"place_on_bed": True, "centre": True}`. Beim ersten Import liegt das Teil
  also auf dem Bett; die Zeilenangaben `ops.py:53–57` und `loader.py:161` sind
  veraltet.
- **`announce()`** schreibt weiterhin nur in `_announcement` und die
  Statuszeile — und versteckt zusätzlich den `reveal_export`-Knopf
  (`main_window.py:15358–15384`). Der Befund „ein zweiter Ort existiert nicht"
  hält; die Zeilenangabe 5180–5199 nicht.
- **Merkmalsbeschriftungen** stehen weiter mit `always_visible=True`, heute in
  `viewport.py:8751–8760` statt 2765–2783.

---

## 4. Wettbewerb: belegte Vergleichsfunktionen und offene Abgrenzung

Aus Primärquellen der Hersteller, Stand 19.09.2026. Die Belege stehen in der
Agentenauswertung unter den Sonden; hier die Folgerungen.

**Was die ausgewerteten Quellen nicht als vollständige gleichwertige Funktion belegen:**

Diese Recherche ist kein vollständiger Marktausschluss. Aus einer fehlenden
Beschreibung folgt nicht, dass kein anderes Produkt den jeweiligen Weg
anbietet; ein Alleinstellungsanspruch benötigt eine eigene vollständige Prüfung.

1. **Dieselben Merkmalshandlungen auf Netz und B-Rep.** Fusion, Shapr3D,
   Onshape und Plasticity bieten am Netz keine Bohrung mit Maß, keine
   Verrundung an einer Netzkante, keinen Zapfen als Merkmal. Onshapes Mixed
   Modeling lässt das Netz Netz und erlaubt Boolean, Shell, Hole, Split
   darauf; NX arbeitet auf Facetten ohne analytische Kanten. Analysis Situs
   erkennt Bohrungen, Zapfen und Fillets nur auf B-Rep.
2. **Deterministischer Nachbau als Operationsfolge ohne Lernverfahren.**
   Fusion *Prismatic* liefert einen B-Rep mit verschmolzenen Flächen, keine
   Features; SolidWorks *Segment Imported Mesh Body* und *Surface From Mesh*,
   NX *Detect Primitives* und Creo *Restyle* liefern Referenzflächen, keine
   Historie. Was Historie liefert, ist KI: das Backflip-Add-In für Fusion
   (seit 04.08.2026, Drittanbieter, Cloud) und Autodesks *AutoTimeline*
   (AU 2026, Auslieferung laut engineering.com 2027). Beides bestätigt §15
   Nr. 6 als bewusste Abgrenzung. „Lokal, deterministisch, ohne Konto“
   bleibt Solidons gewählter Produktvertrag; daraus folgt kein belegter
   Markterfolg — das gehört in `konzept-wettbewerb`.

**Was Standard ist und im Plan steht:** variable Verrundung, Fase in drei
Modi, Schale mit gewählten Öffnungen (Fusion, Onshape) — P6.1 bis P6.3.

**Was Standard ist und im Plan fehlt:**

- **Segmentierung mit Winkel- und Toleranzparametern und Handkorrektur, dann
  Konvertierung in einen B-Rep mit verschmolzenen Flächen.** Fusion (Face
  Groups + Prismatic), SolidWorks (Segment + Surface From Mesh) und FreeCAD
  (Manual Segmentation) machen genau das. Konzept §8.1 verwirft das Nähen,
  weil „die Rundung nicht zum Zylinder wird" — geprüft wurde aber nur
  `UnifySameDomain`, nicht der Zylinderfit auf eine Facettengruppe. Das ist die
  Zwischenstufe zwischen §8.1 und §8.2: **STEP-fähiger exakter Körper ohne
  Verlauf.** Sie ist deutlich kleiner als P4.1–P4.3, hat einen eigenen
  Kundenweg („importierte STL als STEP weitergeben") und wäre ein belastbarer
  Vorversuch für die Fits aus P1. Vorschlag: als P4.0 aufnehmen, ohne
  Entscheidung 7 und 14 anzutasten.
- **Eine Abweichungskarte Fit gegen Netz.** Onshape zeigt bei *Constrained
  Surface* die Abweichung an, Geomagic ebenso. Das Konzept verlangt „Näherung
  sichtbar" nur als Satz. Die Analysekarten aus Bauplan §18.4 haben den Platz;
  eine Karte „Formabweichung" wäre die zweite Kodierung für jedes erkannte
  Maß und die Abnahmehilfe für P1 und P4.
- **Boolesche Operationen Netz × B-Rep ohne Konvertierung** (Onshape, NX,
  Shapr3D). Die Matrix hat die vier Booleschen nicht gefahren; ob Solidon den
  exakten Körper hält, wenn der zweite Eingang ein Netz ist, bleibt offen und
  gehört in die Handlungsmatrix von P2.

**Bibliotheken:** Die Empfehlung „vorhandenes OCCT zuerst“ bleibt.
Die Recherche belegt keinen bereits geeigneten Produktbaustein für die
vollständige Rekonstruktion; sie beweist nicht, dass kein anderes
lizenzgeeignetes Werkzeug existiert. `Matthewjg95/mesh2cad` (MIT) bleibt
Vergleichskandidat für Platten/Gehäuse, mit den vom Projekt beschriebenen
Geometrievereinfachungen. Sanaxen hat ebenfalls eine MIT-Hauptlizenz, aber
eine ungeklärte transitive Kette; Danxtream beschreibt ein proprietäres
Programm, dessen erlaubte kommerzielle Nutzung keine belegte Einbettungs-
oder Weitergabeberechtigung darstellt. Einzelquellen und Nachweise stehen
im Konzept §13.8.1.

Bei `planegcs` 0.8.0 lautet der Paketbefund präzise: LGPL-2.1-or-later,
keine gelisteten 3.14-/macOS-Wheels, jedoch Quellpaket und Bauhinweise;
keine Aussage bewiesener technischer Unverträglichkeit.
[Paket/Bauhinweise](https://pypi.org/project/planegcs/0.8.0/).
CadQuerys Sketch-Solver wurde als experimentell mit acht Bedingungsarten
recherchiert. Der eigene Löser bleibt, bis ein Vergleich eine konkrete
Lücke und einen tragfähigen Ersatz belegt.

---

## 5. Das Bedienprotokoll und sein Register

`konzept-bedienung.md` trägt seit dem 20.08. vier Punkte als „unverändert
offen". Heute:

| Punkt | Stand 19.09. | Im Register |
|---|---|---|
| Import legt nicht auf die Platte | **teilweise überholt** — das erste Modell liegt seit `plan.py:246` auf dem Bett, weitere nicht | nein |
| Kein Absturzprotokoll (`excepthook`, `faulthandler`) | offen — kein Treffer in `app/` | nein |
| Merkmalsbeschriftung nur dauerhaft, nicht beim Überfahren | offen (`always_visible=True`) | nein |
| `announce()` nur in der Statuszeile | offen | nein |

Keiner der vier steht in `ROADMAP.md`. Das widerspricht dem Satz, der über
dem ganzen Verzeichnis steht: *Offene Arbeit steht im Register und nirgends
sonst.* Die Entscheidung gehört Robert: je Punkt **eintragen oder streichen**
— streichen mit Begründung im Protokoll, nicht durch Schweigen.

---

## 6. Kritik am Plan

### 6.1 Zwei Kundenfehler von heute warten auf „nach 0.4.3"

Beide sind gemessen, beide sind klein, beide treffen jeden Kunden, der die
Operation benutzt — und beide stehen als Paket P2.1 hinter der Veröffentlichung.

- **Spiegeln verwaist die Merkmale eines exakten Körpers still.**
  `mirror_object` hält den Solid über `moved_body`, gibt aber `features={}`
  zurück (`geom/ops.py:646`); `_carried_along` reicht leere Merkmale
  unverändert durch. Passungen, Referenzen und die Auswahlkarte verlieren die
  Bohrungen, ohne dass der Prüfbericht eine Zeile schreibt. Die Drehung hatte
  denselben Fehler und ist am 17.09. mit `5ad173de6` behoben worden — mit
  demselben Mechanismus lässt sich die Spiegelung nachziehen.
- **Skalieren hinterlässt doppelte Flächen mit falschen Maßen — am Netz.**
  Das ist kein B-Rep-Thema: Ein skalierter Netzquader trägt 12 Flächen, sechs
  davon mit den alten Inhalten an verschobenen Mittelpunkten. Wer danach eine
  Fläche wählt, kann die alte treffen. Der Minimalfix ist nicht die exakte
  Skalierung, sondern: Nach einer nicht starren Transformation die
  mitgeführten alten Merkmale nicht neben die frisch erkannten stellen.

Vorschlag: beide wie `CYLINDER_SPREAD` und die Drehung als **vorgezogene
Korrekturen** behandeln (Konzept §13.2, „bereits erledigt"), die Abnahme
„Skalieren exakt" bleibt bei P2.1. Das ist die Doktrin „beheben statt
notieren" — und beides ist mit `affected_tests` in einem Schritt prüfbar.

### 6.2 Reihenfolge innerhalb des Plans

Die Prioritätentabelle der Recherche (§1) setzt vier Dinge auf Rang 1:
Merkmale nach Änderungen erhalten, importierte Form erkennen, Maß und Passung
trennen, gleiche Handlung auf beiden Kernen. Die Paketliste des Konzepts
beginnt mit P0 (Bedienung). §13.6 erklärt P0.1–P0.4 für unabhängig — sagt
aber nicht, womit nach 0.4.3 **begonnen** wird. Aus den Messungen folgt eine
Reihenfolge:

1. **P2.1 und P2.3 zuerst.** Nachführung (§6.1) und kanonische Erkennung: Die
   API-Sonde zeigt, dass OCCT die Arbeit bereits macht; P2.3 ist
   Anschlussarbeit an `brep/features.py`, keine Forschung. Beides beseitigt
   Fehler, die heute STEP-Kunden treffen.
2. **P1.1 daneben.** Der Zylindermaßvertrag ist der Befund mit der größten
   Breite (jede Bohrung jedes importierten STL misst zu klein — das Ø5,19 aus
   der nativen Fahrt ist genau dieser Fehler bei 48 Facetten).
3. **P0.3/P0.4 parallel**, weil sie die größte Bedienänderung sind und ihre
   Verträge (§10.2, §10.3) fertig geschrieben vorliegen.

### 6.3 P6/P7 ohne Bindung an das Umschaltpaket

§13.6 bindet P2.8 (Kernwahl-Haken fallen) an „P2.1–P2.7 grün". P6 und P7
hängen nur an P0.3/P0.4 und P3. Damit können 15 neue Operationen entstehen,
bevor die Parität der bestehenden 57 steht — jede davon müsste sofort auf
beiden Kernen gebaut werden, sonst wächst die Einbahnstraße mit. Vorschlag:
**kein P6-Paket beginnt vor P2.8**, und jede neue P6-Operation liefert ihre
Zeile in der Handlungsmatrix mit.

### 6.4 Oberflächengrenzen sind die Randbedingung, nicht die Fußnote

Datei-Menü 12/12, Vorderseite 8/8 (Konzept §9.5). P3.3 („Neue Ebene …"),
P6.5a–c (Schnittvarianten), P6.7 (Muster) und P7.4 (STEP-Auswahl) bringen
Einträge und Felder mit. Das Konzept sagt für die Versatzebene, wo sie
hingehört (ein Feld im Skizzeneditor, kein Menüeintrag); für die anderen
sagt es nichts. Vor P6 gehört eine Zeile je Paket: welches Menü, welche
Gruppe, welche Vorderseite — und `test_interface_limits.py` bleibt grün.

### 6.5 Das Dokument selbst

1604 Zeilen, fünf Fassungen, drei Gegenprüfungsabschnitte (§§16–18), und die
verbindliche Paketliste steht in der Mitte (§13.2). Das ist als
Begründungsgedächtnis richtig und als Arbeitsgrundlage schwer. Zwei kleine
Eingriffe reichen: Ein Satz im Kopfkasten, welche Abschnitte verbindlich sind
(§13.2, §13.6, §14) und welche belegen; und **RM-188 trägt die Paketliste
selbst**, nicht als Verweis — sonst gilt der Registersatz aus §5 auch hier
nicht. (Eingearbeitet am 19.09. als Liste mit Stand je Paket; ein Kästchen
je Paket wäre für den Registertest ein eigener Punkt gewesen.) §10.2
wiederholt Recherche §4.2 in drei Absätzen; ein Verweis genügt.

---

## 7. Empfehlungen, geordnet

| Nr | Was | Warum | Stand 19.09. |
|---|---|---|---|
| 1 | Spiegelung und Skalierungs-Doppelung als vorgezogene Korrekturen | Kundenfehler heute, Fix jeweils klein, Mechanismus vorhanden (§6.1) | **P0.0**, erstes Paket |
| 2 | Die vier Punkte aus `konzept-bedienung` je eintragen oder streichen | Registerregel (§5) | **P0.7**, alle vier |
| 3 | Reihenfolge festlegen: P0.0, dann P2.1, P2.3, P1.1, parallel P0.3/P0.4; P6 nicht vor P2.8 | §§6.2–6.3 | **§13.10** |
| 4 | P4.0 „Netz → exakter Körper ohne Verlauf" als Vorstufe | Standard bei Fusion/SolidWorks, kleiner als P4.1–4.3, eigener Kundenweg (§4) | **P4.0** |
| 5 | Karte „Formabweichung" zu P1 | zweite Kodierung für Näherungen, Abnahmehilfe (§4) | **P1.6** |
| 6 | Boolesche Ops Netz × B-Rep in die Handlungsmatrix | nicht gemessen (§4) | in **P2.1** |
| 7 | Historische Empfehlung: Open3D für macOS ausschließen; inzwischen auf fehlenden fertigen Intel-Paketweg präzisiert. Analysis Situs als Portierung führen | §§3.2–3.3 | Konzept §11/§13.8.1, Recherche §5 |
| 8 | Zählungen und Zeilenangaben nachziehen (§3.1) | Dokumentpflege | an den Stellen, Verzeichnis in Konzept §19 |
| 9 | Handlungsmatrix `s8_matrix.py` als Test übernehmen | Sie ist die Abnahme, die §5 verlangt | in **P0.0/P2.1** |

---

## 8. Nachweise

Alle Sonden mit der `.venv` des Hauptklons, Nutzerverzeichnisse in einen
`iso`-Ordner umgebogen, Ausgaben in Dateien, Exit-Code unmittelbar gelesen.

```text
s1_register.py     Exit 0   Register, Bausteine, Merkmalsarten, Bedingungen, Signaturen
s1b_schemas.py     Exit 0   Parameterschemata der 28 Ops des Kundenwegs
s2_mirror_scale.py Exit 0   Spiegelung und gleichförmige Skalierung, beide Kerne
s3_nurbs.py        Exit 0   NURBS-Erkennung, CanonicalRecognition, SurfToAnaSurf
s4_radius.py       Exit 0   Radiusreihe, neun Zeilen
s5_placement.py    Exit 1   Ø0,5 gemessen wie beschrieben; der zweite Fall (Ø5,2)
                            scheiterte an der Sonde — der Prüfpunkt lag im Loch
s6_project.py      Exit 0   Projektion an sechs Flächen, verschobene Ebene
s7_edgekey.py      Exit 0   Kantenschlüssel vor und nach Verschiebung
s8_matrix.py       Exit 0   Bauart-Matrix über 132 Ops, Kundenweg, X-Skalierung
```

Die externe Recherche lief über zwei Agenten mit Primärquellen (PyPI-JSON,
OCCT-Refman und -Quelltext, GitHub-Releases, Hersteller-Hilfen); ihre
Auswertungen liegen in den Sitzungsprotokollen, die Folgerungen in §§3–4.
Nicht wiederholt: Klickzahlen, native Fensterfahrt, Prototyp-Fits,
Filament-Rack, HLR — sie bleiben historische Angaben vom 17./18.09.
