# CAD-Übergabeinventur vor Abschluss P1.4c.1

Lesender Schnappschuss vom 20.09.2026 auf `859b75e0ee0d081c8339313757666ac674d845b1`.
Nur diese Notiz wurde geschrieben; keine Tests, Sonden, Tore oder Git-Mutationen.
Die Hauptaufgabe schließt P1.4c.1 noch ab. Dessen endgültigen Commit, direkten
Tor-Exit, Prüfzahlen und verbleibenden Arbeitsbaum **vor der dauerhaften Übergabe
ergänzen**. Der Benutzer will anschließend die vollständige Übergabe an eine
neue Sitzung und das Ende dieser Sitzung, keinen weiteren Umsetzungsschritt.

## 1. Maßgeblicher Stand und erledigter Umfang

`ROADMAP.md#rm-188` ist die aktuelle Arbeitsliste. Das CAD-Konzept §13.10 legt
die Reihenfolge fest; Tabellenzeilen mit „geplant“ in §13.2 sind keine jüngere
Statusquelle. Die vier ursprünglichen Dokumente bleiben die fachliche Grundlage:
`konzept-bedienung.md`, `recherche-cad-paritaet-2026-09.md`,
`konzept-vollwertiges-cad-2026-09.md`, `durchsicht-cad-konzepte-2026-09.md` unter
`konzepte/`. Die Durchsicht ist eingearbeitet; historische Befunde daraus nicht
ungeprüft erneut als offene Umsetzung behandeln. Vor Änderungen zusätzlich
`AGENTS.md`, passende `CLAUDE.md`-Karten, `.claude/rules/` und
`.claude/memory/MEMORY.md` lesen. Gemeinsame fachliche Regeln und UI-Wege
weiterverwenden; keine zweite Geometrie-/Maß-/Zuordnungswahrheit erzeugen.

| Paket | Aktuell abgeschlossener Umfang | Verbleibende Grenze |
|---|---|---|
| P0.0 | Gemeinsame Merkmalstransformation, keine Doppelmerkmale, gerichtete Gewinde; `cfc5e303` | Spätere Fensterprüfungen nur Release |
| P0.5 / P0.6 | Werkzeugauswahl §13.8.1 erledigt; vorhandener Cythonweg ausreichend | Konkrete Machbarkeit je Fachpaket; keine Freigabe neuer Infrastruktur oder P5.3 |
| P0.1 / P0.2 | Positionsfelder, Texte, Sperrgründe; gemeinsame Konvertierungs-/Vorschau-/Auftragsprüfung für Menü, Agent und Bedienwege; `064e3095`, `77223ccb` | Implementiert, Release-Abnahme offen |
| P0.7 | Früher UI-/CLI-Absturzschutz, redigierte Supportdaten, passive Quittung, Hoververtrag, unveränderte Importlage und rücknehmbarer Gruppen-Bettversatz; `7aaa993d`, `b9b96a91`, `47023b53` | Implementiert, Fenster/DPI/Tastatur/Bildschirmleser offen |
| P1.1 / P1.2 | Konturen und reale axiale/radiale Maße; Kegel, Kugel, Torus einschließlich nativer/rationaler Träger, Teilflächen, Quellen, Cache, STEP, Undo; `db7d1a5c`, `851f913a` | Implementiert, Release-Abnahme offen |
| P1.3 | Ganze Körperprobe radialer und bündiger Passungen, aktuelle Einbaulage, native Originale geschützt, gemischte Näherung, Abbruch bis Export; ehrliche Drucklagen in Beispielen/Tour; `eeadc09b`, `912789f7` | Implementiert; Pressverformung, Montageweg und Flächenkontakt werden nicht behauptet; Release-Abnahme offen |
| P1.6 | Formabweichung aus vorhandenen fünf Trägerarten, Originaldreiecke, numerische Klammer und baryzentrischer Zeuge, unbekannte Abdeckung, Quellen/Cache/UI; `5d451fe7` | Implementiert; keine neue Fitrechnung, keine Nennmaßunsicherheit; Release-Abnahme offen |
| P1.4a / P1.4b | Räumliche Vorauswahl, durchgängiger Abbruch, konkurrierende Identitäten als ganze körperbezogene Entscheidung, Injektivität und Nichtfortführung, atomare Antworten, Format 27, merkmalsgebundener Folgecache; `d483e1477`, `fe17cd3bc` | P1.4 insgesamt läuft; native Neuwahl offen; Produktionsgrenze weiterhin **1000** |
| P2.1 / P2.2 | Exakte affine Wege und nachgeführte native Flächen; native Filamentattribute, Builder-Farbfortführung, Cache und Historie; `77223ccb`, `3df89b8e` | Implementiert, installierte Plattformen/Fenster offen; Farbhistorie ist kein allgemeiner Identitätsbeweis |

Letzter abgeschlossener Gesamtbeleg: `p14b-published.json` nennt
**12.971 bestanden, 26 übersprungen, Suite/Ruff/Format/mypy jeweils Exit 0**,
ROADMAP-Anschluss 152 bestanden, Push Exit 0 und überprüftes remote/main
`859b75e0e`. Das ist der Entwicklungsstand von P1.4b, kein Beleg des danach
veränderten P1.4c.1 und keine Release-Abnahme. Zuletzt zusätzlich
`930ccbbc5`: Manifestprüfung vom letzten lokalen Releasebau entkoppelt.

Noch offen bzw. erst teilweise umgesetzt:

- **P0.3/P0.4 laufen:** erster gemeinsamer Bohrungs-Maßeditor und echte Bezüge
  stehen (`852de666`, `1fc131a6`, `102d4bf7`); vollständige Felder, Griffe,
  Gruppen, Merkmale und historische Bedienwege fehlen. Achsen/Symmetrie P1.5,
  dauerhafte Bezüge P3.2, Familienübertragung P5.1.
- **P2.3 läuft:** Ebenen, Zylinder, Innenräume, Ringe/Kugeln und rationale
  Träger belegt; vollständige Semantik-/Teilflächenparität und weitere
  Trägerfamilien fehlen. Das ist Voraussetzung und Teil der Zwillingeprüfung.
- **P1.4c läuft als nächster Anschluss; P1.5 offen.** P1.4c.1 ist unten eng
  abgegrenzt. Mehr als 1000 Flächen sind in echten STL-/STEP-Lebensläufen
  funktional geprüft; das ersetzt keine gemessene Produktionsgrenzenerhöhung.
- **P2.4–P2.6 offen; P2.7 Machbarkeit belegt, Produktion offen; P2.8 offen.**
  Kernwahl-Haken erst nach grüner Handlungs-/Bausteinmatrix entfernen.
- **P3.1–P3.5 offen:** skizzeneigene Ebenen, dauerhafte Rahmen/Referenzen,
  Ebenenauswahl, Flächenkontur, exakter Ebenenschnitt.
- **P4.0–P4.3 offen:** Netz→exakt, Nachbaukandidaten, unabhängige Formprüfung,
  atomare Übernahme hinter dem Import.
- **P6.1–P6.7 offen:** variable Rundungen, erweiterte Fasen, Öffnungsflächen,
  Formschräge, Schnitt durch Drehen/Pfad/Überblenden, Kurven/Bedingungen,
  Merkmalsmuster. **P7.1–P7.4 offen:** Einfügen/Umsortieren/Unterdrücken und
  STEP-Mehrkörperimport mit Namen, Farben, Instanzlagen.
- **P5.1–P5.3 offen:** vollständige Maßbedienung, Fenster-Auswahlmatrix und
  installierte Gesamtabnahme Windows/macOS/Linux. P5.3 bleibt Voraussetzung
  für Hochladen, keine Veröffentlichung ist durch diese Übergabe beauftragt.

## 2. Konkreter Einstieg nach P1.4c.1

Zuerst `p14c-implementation-order.md` lesen. Es präzisiert die älteren drei
Pläne und Reviews; insbesondere bedeutet der aktuelle **erste Schritt** die
sichere native Vollflächenübergabe. Die ältere `p14c-evaluation-boundary.md`
bespricht einen möglichen ersten Validierungsschritt und ist kein Beleg,
dass dieser schon implementiert wäre.

### P1.4c.1: gegen den endgültigen Commit abgleichen

`app/core/brep/kernel.py::Solid.checked_face_indices`,
`complete_faces_of_triangles` und private Kopierabbildungen sichern die
tatsächliche aktuelle Auswahl. `brep/profiles.py::push_faces` und
`brep/edit.py::unround` bekommen `selected_faces`; `None` bezeichnet den
bisherigen unbenannten Modus. Leere/ungültige ausdrückliche Auswahl darf
niemals in diesen Modus fallen. `geom/face_ops.py::_on_a_solid` und der
Entfernen-Zweig `geom/prepare_ops.py::_exact_fillet` müssen genau diese
vollständigen Originalflächen weiterreichen. Tests: `test_mesh_faces.py`,
`test_prepare.py`, `test_solid_ownership.py`. Dieser Anschluss verlangt
**keine Projektmigration, keine neue Antwortpersistenz und keine neue UI**.
Radiuswechsel über Entfernen→scharfe Kante→neue Rundung bleibt gesondert offen.

### Danach: native Identität, Fortführung und Gruppenwahl

- Einstieg `app/core/scene/evaluate.py`, `scene/orphans.py`, `app/core/types.py`,
  `scene/cache.py` und `geom/prepare_ops.py::_preserved_exact_features` samt
  vorhandenem `resize_hole`-Nachweis. `touches_features`, gleiche Namen,
  `created_by`, `provenance` oder Filamentwerte beweisen keine Fortführung.
  `Feature.face_indices` sind Tessellationsdreiecke, keine nativen Slots.
- Der enge körper-/ausgabequalifizierte Produzentenbeleg muss wie `transform`
  durch **OpResult, warmen Rohcache und Diskcache** reisen. Nicht als zweiten
  Namensdienst im Projekt speichern. Nach tatsächlicher Änderung benötigte
  alte Bezüge prüfen: verloren, ungeprüft oder nur frisch gleich benannt
  bleibt offen. `orphans.pending_references` berücksichtigt die Lebensdauer;
  bereits früher verbrauchte Bezüge sperren spätere Entfernung nicht.
- Fehlender nativer Identitätsbeleg muss strukturiert bis zum Orphan-/Session-
  Anschluss reichen; keine scheinbare Reparatur gegen den alten Körper vor
  dem fehlgeschlagenen Erzeuger. Der bisherige native Matchweg übernimmt
  **Erzeuger**, keine generische Netz-Umbenennung der nativen Topologie.
- Gemeinsame Antwortenquelle erhalten: `perceive/matching.py` für Geometrie,
  `require_injective`; `match_records.py` für Schema/kanonische Schlüssel;
  `match_decisions.py` für ganze Gruppen, Wiedererkennung, atomare Wahl.
  `Feature`/`SurfacePatch` und vorhandene Codec-/Hashhelfer weiterverwenden.
- Native Gruppen erhalten eigene Domäne und engen Erzeugerscope; Netzgruppen
  werden nicht zu nativer Zustimmung. Scope aus rohem Erzeugerschlüssel und
  Ausgabeindex, **nicht** aus dem nach der Wahl erzeugten Objekthash. Echte
  aktuelle Auswahlfähigkeit und vollständige Wiedererkennung zusätzlich prüfen.
- Im Inventurstand ist **Projektformat 27, Cacheformat 20**. **Format 28 ist
  geplant, nicht schon vorhanden:** eigener Schritt 27→28 in
  `scene/migrations.py`, Schema in `scene/project.py`/`match_records.py`, alte
  v27-Datei plus Haupt-/Undo-Seiten. Alte Gruppen unverändert lesbar halten,
  keine erfundene native Zustimmung/Scopewerte migrieren. Der tiefe
  `serialise.py`-/`History.record_matches`-Weg besteht bereits.
- `fingerprint.diameter` ist historisch der **Rohwert** `feature_vector[6]`
  (bei Flächen sogar Fläche), kein normiertes Maß. Nur Positionen sind relativ.
  Keine semantische Umdeutung beim Schemaausbau.

### Kantenentscheidungen bleiben ein weiterer, eigener Anschluss

Einstieg `geom/edge_ops.py`, `brep/edit.py::named_edges/wanted`,
`registry/params.py` für `kind="edges"`, `scene/evaluate.py` vor
`cache.get`, `scene/hashing.py`, `ui/session.py`, `ui/main_window.py`,
Frage-/Vorschauweg und `ui/labels.py::edge_label`.

Eine eindeutige andere Kante kann über bestehende Parameterantworten gewählt
werden. Zwei tatsächliche Kanten mit gleichem gerundeten Schlüssel brauchen
unterschiedliche Fragetoken und echte Auswahlübertragung zur privaten Kopie;
erneutes Nachschlagen desselben Schlüssels löst die Kollision nicht. Eine
persistierte ganze Kantenwahl gehört zu **Eingang + registriertem Feld +
vollständigem Auswahlbündel** der konsumierenden Operation. Sie muss vor deren
Cachezugriff aufgelöst werden; der tatsächlich aufgelöste Selektor geht in
ihren Schlüssel ein. P1.4b-Ausgabehash allein genügt hier nicht. Scope ist
kein Kurven-/Trimmbeweis. `carried_face_slots` und verfügbare Builder-History
sind noch kein Beleg des Radiuswechsels. Keine Kante als FeatureId tarnen.

Danach P1.5 nach `p15-entry-plan.md`, `p15-geometry-review.md` und
`p15-consumer-review.md`: gemeinsame `relations`, `FeatureActionGroup`,
Originalträger und Maßquellen. Belegter offener Unterschied: Netzfilter
`MIN_FACE_AREA=4.0` gegen native kleine echte Flächen; 1056-Testkörper wurden
deshalb mit 2-mm-Kanten gebaut. Keine globale Toleranzänderung daraus ableiten.

## 3. Dauerhaft zu übernehmende State-Unterlagen

**Der gesamte hiesige State-Ordner ist untracked.** Ein Folgeklon bekommt
keine dieser Dateien. Die Hauptaufgabe muss die folgenden konkreten Inhalte
in eine dauerhaft eingecheckte Handoff-Ablage übernehmen und dort relative
Verweise herstellen. Diese Inventur kopiert oder committet sie nicht.

| Priorität / Thema | Zu erhaltende Dateien in diesem Ordner |
|---|---|
| Unmittelbarer Einstieg | `p14c-implementation-order.md`, `p14c-native-reference-plan.md`, `p14c-evaluation-boundary.md`, `p14c-persistence-review.md`, `p14c-ui-kernel-review.md`; endgültige P1.4c.1-Abschlussnotiz und Belege nachtragen |
| P1.4b fachlicher Vertrag | `p14b-contract-review.md`, `p14b-answer-contract.md`, `p14b-numerics-implementation.md`, `p14b-numerics-review.md`, `p14b-answer-review.md`, `p14b-integration-review.md`, `p14b-root-integration.md`, `p14b-published.json` |
| Echte Bindungs-Cachekorrektur | `p14b-follow-cache-probe.py`, `p14b-follow-cache-two-claims.txt`, `p14b-follow-cache-two-claims-green.txt`, `p14b-feature-hash-proof-path.txt`: unveränderte Zwei-Ansprüche-Sonde rot→grün, Marker links/rechts und wirklicher Folgecachetreffer. `p14b-follow-cache-red.txt` enthält einen früheren Sondenfehler, **keinen** eigenständigen Produktrotbeleg |
| P1.4a Herleitung und Grenzen | `p14-entry-plan.md`, `p14-matching-implementation.md`, `p14-review-notes.md`, `p14-review-cases.py/.txt`, `p14-review-final-probe.py/.txt`, `p14-competing-identities-plan.md`, `p14-root-integration.md`. Letztere enthält einen damaligen roten Zwischenlauf; abgeschlossenen Stand aus Commit/ROADMAP lesen |
| P1.6 numerischer Beweis | `p16-contract.md`, `p16-extrema-plan.md`, `p16-extrema-review.md`, `p16-deviation-implementation.md`, `p16-deviation-plan.md`; wichtig: reale baryzentrische Zeugen, garantierte L/U-Grenzen, feste Gesamtarbeit, endlicher Abschluss oder unbekannt |
| P1.6 Verbraucher/Träger/UI | `p16-carrier-plan.md`, `p16-carrier-implementation.md`, `p16-root-integration.md`, `p16-ui-plan.md`, `p16-ui-freeze.json`, `p16-producer-cancel-red-full.txt`, `p16-producer-cancel-green.txt`, `p16-corpus-map-probe.py/.json/.txt` |
| P1.2/P1.3 Vorgeschichte mit verbleibenden Grenzen | `p12-measurement-plan.md`, `p12-mantle-support-plan.md`, `p12-native-progress.md`, `measures-stage-review-2026-09-20.md`, `p13-collision-plan.md`, `p13-measure-status-plan.md`, `p13-flush-plan.md`, `p13-flush-implementation.md` |
| Nächste Semantik-/Bedieneinheiten | die drei `p15-*.md`, `next-p03-contract.md`, `p03-progress.md` |
| Parallelauftragsgrenze | `prompt-parallel-p2-5.md`, `prompt-parallel-p2-7.md`; sie autorisieren Prototyp-/Nachweisordner, keine Produktionsintegration |

Die Pointer `*-path.txt`, `*-dir.txt`, `*-evidence-path.txt` und die drei
`*development-gate.txt`/`current-cad-commit-gate.txt` ersetzen keine Belege:
Sie zeigen auf löschbares `%TEMP%`. Vor Übergabe ausgewählte Logs mit direkten
Exitcodes, Referenzsonden, geprüften Hashes und Kommandos mit übernehmen.
Insbesondere:

- Letztes grünes Tor:
  `C:/Users/rober/AppData/Local/Temp/solidon-cad-competition-final-789c0cf656654dc395e84d2ce8513a4d`.
- P1.4b numerische Rot-/Grünbelege: `p14b-numerics-proof-path.txt` und
  `C:/Users/rober/AppData/Local/Temp/solidon-p14b-matcher-review-49abf3e6327c46f198935ee8ff8743ea/`
  mit `resolve_probe.py`, `resolve-red.txt`, `resolve-after.txt`.
- P1.6 numerischer Abschlussfehler:
  `C:/Users/rober/AppData/Local/Temp/solidon-p16-numerics-review-8e2c8a56019d42eaac8c07d2fbd1e895/`
  mit `review.md`, `overflow.py`, `overflow.txt`, `overflow-after.txt`; dazu
  `p16-deviation-evidence-path.txt`, `p16-carrier-log-dir.txt`,
  `p16-native-cone-log-path.txt` und abgeschlossener Torbeleg im Root-Bericht.
- P1.4c.1: `p14c-consumer-red-proof-path.txt` plus die noch entstehenden grünen
  Consumer-/Kernel-/Gesamttorbelege. Die jetzigen `p14c-*.patch` und
  `*-base.json` sind Zwischenstandsübertragung; nach dem finalen Commit
  **nicht blind wieder anwenden** und nicht als einzigen Implementierungsbeleg
  übernehmen.

Keine pauschale Aufnahme des State-Verzeichnisses: generierte
`*.userdata/RS Digital/Solidon3D/activation.state`, `trial.json`, Probe-Caches
und sonstige Benutzerverzeichnisse gehören **nicht** ins Handoff. Auch
`prepare_*gate.py`, `record_*commits.py` und alte Finalisierungsskripte sind
historische Hilfen, keine automatisch auszuführenden Folgeaufträge.

## 4. P2.5, P2.7 und aktuell fremde Arbeit

**P2.7:** `69efc1cdf`/`469ef4e92` und der getrackte Ordner
`konzepte/nachweise-cad-p2-7/` belegen Machbarkeit, nicht Produktionsparität.
README, `pruefkoerper.md`, Sonden und `laeufe.txt` zusammen lesen. Elf Sonden,
568 Zusicherungen; alle 35 Einsetz- und zehn Erzeugungspfade konvertieren.
Ein Formvertrag mit zwei Auswertern bleibt das Ziel. Integration muss die
vier Befunde tragen: verschwundener Gewindegang, ungültige STEP-Senkköpfe,
Fuzzy-Absturz an gemeinsamem Eingang versus private Kopien, nach Schnitt
neu vergebene Namen mit falschem zweiten Ziel. Die im Prototyp bewahrten
Trägernamen brauchen zur Integration den tatsächlichen Fortführungsbeleg
aus P1.4c/P1.5, keine ungeprüfte Kopie alter Merkmalsdreiecke. Bereichs-, Fenster-, Leistungs- und
integrierte Kundenabnahme bleiben offen.

**P2.5:** Die unabhängige Sitzung schreibt ausschließlich
`konzepte/nachweise-cad-p2-5/`; im Snapshot komplett untracked. Ihr README
auf Basis `d483e1477` liegt bereits vor und grenzt sich ausdrücklich als
Prototyp ab. Beim Lesen nennt `laeufe.txt` S1/S2/S3 mit Exit 0; README enthält
bei S4 noch `{{S4}}`. Daher **noch kein abgeschlossener Bericht-/Commitbeleg**
und erst recht keine Erledigung des Produktpakets. Vor Übernahme den finalen
Bericht, vollständige direkten Ausgänge und Pathspec-Commit abgleichen.

Der Prototyp misst Gewinde ohne Erzeugerwissen aus STEP; die spätere
Produktintegration gehört in bestehende Feature-/Quellen-/Trägerwege.
Wesentliche Anschlussbefunde: Links-/kurze Gewinde fehlen im Netz, Gangtiefe
ist tessellationsabhängig falsch, Gewindepassung benötigt einen fachlich
begründeten Messvertrag, Erkennbarkeit erzeugter Gewinde ist zu entscheiden,
Nenn-Ø innen meint Grund-Ø und beide Radien bleiben unterscheidbar. Der
berichtete stille Gangverlust bei halbzahligen Längen überschneidet sich mit
P2.7; **ein gemeinsamer Fix**, keine zwei Erzeugerwege. Genannte
Unsicherheitsvorschläge vor Integration gegen den bestehenden Maße-/Fitvertrag
prüfen. Gegenstück/Normgrößenvorschlag bleibt **P2.6**. Fremdes Hersteller-STEP,
drei und mehr Gänge, links/mehrgängig innen, konische und kantenlos tangential
modellierte Gewinde sind im Prototyp noch offen.

Aktuell gemeinsam veränderter Baum bei der letzten Inventur: `brep/edit.py`,
`brep/kernel.py`, `brep/profiles.py`, `tests/test_mesh_faces.py`,
`tests/test_prepare.py`, `tests/test_solid_ownership.py`; anschließend auch
die fünf `app/i18n/locales/{en,es,fr,it,pt}.json`. Das sind Arbeiten der
Hauptaufgabe und ihrer Kernel-/Textverantwortlichen, nicht Änderungen dieser
Inventur. Consumer-/Kartenergänzungen können bis zum Freeze dazukommen.
Keine fremden Änderungen zurücksetzen oder in einen sachfremden Commit nehmen;
für jeden Commit explizite Pathspec. `website/` weiterhin unangetastet.

**Arbeitsregel für die Nachfolgesitzung:** gezielte funktionale Kern-/Statik-
prüfungen während Entwicklung, Entwicklungstor vor Commit. Ganze
Fensterdateien einschließlich gefilterter/offscreen Teilmengen sowie
Leistungsprüfungen ausschließlich beim Release. Ein zurückgestellter
Fensterfall ist nicht bestanden. Handoff zuerst auf finalen Stand bringen,
dann diese Sitzung beenden; neue Umsetzung erst in der Nachfolgesitzung.
