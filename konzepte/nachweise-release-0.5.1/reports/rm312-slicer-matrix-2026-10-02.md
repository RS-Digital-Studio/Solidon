# RM-312 — Sieben-Slicer-Matrix und Creality-Zeitabweichung

## Integrierte Düsenwahl

Die Implementierung ist mit Commit
`8374885aeb61da8becb9c2c8d2f3643568d27a93` in `origin/main` enthalten
(Ancestry geprüft). Die Düsenauswahl verwendet passende Drucker-/Hersteller-
Identität, bietet „Andere …“ und prüft die tatsächlich geschriebene 3MF samt
Gegenprobe gegen die zuvor falsche Profilkennung.

Für diesen Commit liefen 83 gezielte Kernfälle; das damalige vollständige
zentrale Entwicklungstor meldete 18.771 bestanden und 62 übersprungen.
Suite, Ruff, Format und mypy endeten jeweils mit Exit 0. Die funktionale
Sieben-Slicer-Matrix und die native Fensterabnahme beim Release sind davon
getrennte Nachweise und hier noch offen.

## Geprüfter Zwischenstand vom 02.10.2026, 07:51 CEST

Die Sieben-Slicer-Matrix läuft noch. Dieser Stand ist **keine vollständige
Abnahme**. Er hält nur vollständig geschriebene Modellresultate fest; zwei
Arbeiter liefen zum Messzeitpunkt noch.

| Ergebnis | Stand |
|---|---:|
| Vollständig geprüfte Modelle | 52 von 125 |
| Aktive Modelle / noch nicht begonnen | 2 / 71 |
| Ausgewertete Varianten | 839 |
| Druckdatei geschrieben | 747 |
| Fehlgeschlagene Varianten | 92 |

Der Lauf arbeitet zwei Modelle gleichzeitig mit den sieben eingerichteten
Slicerprofilen. Diese Tabelle friert den zentral nachgeprüften Stand ein; die
Matrix lief danach weiter. Unauffällige Kombinationen werden bereinigt; sobald
eine Slicer-Kombination einen bedeutsamen Befund enthält, bleibt ihr kompletter
Arbeitsordner samt allen Varianten zur Diagnose liegen. Die 125 Quelldateien
bleiben lokal; der Bericht enthält weder Modelle noch G-Code oder Prozessdumps.

### Laufidentität

| Merkmal | Wert |
|---|---|
| Quellstand | `129f8ca11b2ffb8f685147fc63b28cbe47697ad5` |
| SHA-256-Codefingerabdruck aus `treiber.py::_code_digest` (405 Quell- und Konfigurationsdateien) | `c91022a8f2bc1c07c2f4ffc5a29fcd639671c10f725c0c111fc76f03fab7ce2a` |
| Lauf-Fingerabdruck | `77253c6797ec3c6d9ed01b336a9ef5296c59b4b30ee27332f1d5955a8ceca606` |
| SHA-256 von `.matrix-identity` | `c60dc47a5b9befafbbf4e5cb0970e29b4830867a89dae11da76a225e2e1246a1` |
| Python | 3.14.7 |
| Modus | `modelle`, 125 Dateien, Profilgruppe `heim`, 2 Arbeiter |
| Ausrichtung / Zeitlimit je Slicer | `1` / 2.700 s |

Der Lauf-Fingerabdruck bindet Codeabbild, Modellpfade samt Eingabe-Hashes,
Slicer-Binärdateien, installierte Profile und Laufparameter zusammen. Die
Dateien mit diesen Rohdaten liegen im lokalen Prüfverzeichnis, nicht im
Repository.

### Eingesetzte Slicer und Profile

Die Versionen stammen aus den installierten Produktmetadaten und
Dateiversionen; ausführbare Dateien und Profilbestände wurden im Lauf gehasht.

| Slicer | Version | Druckerprofil | Programm-SHA-256 | Profildateien / SHA-256 |
|---|---|---|---|---|
| Bambu Studio | 02.08.02.61 | `bambu-p1s` | `7680dac4a953cb4f8a96cc2b4ad4ea0b8bfc62f937d3491256922ff24dbb8268` | 3.589 / `d6c75cb5ea8993fdb6eebd1abf133dbb333b9a9f2736b5b5e58545ea5fa55903` |
| Creality Print | 7.3.0.6149 | `creality-k1` | `bf3b329325f9b8d8319a478c601592d47b9a681592bec0fd0fa7778c19e7f001` | 6.953 / `308205db99ca48af0087c07448aa2c084453eb9abf355e6f6df167a4a730de5b` |
| Cura | 5.13.0 | `sovol-sv06` | `36e36d4618cd09a0cd8802a565c2cdbe54804eb750ac84303a0c6d6f784afde2` | 10.011 / `ad2ba99c954bd362c36d30d3725c6470c09e16dee98fcca934e4ba118c8049b4` |
| ElegooSlicer | 1.5.3.5 | `centauri-carbon-2` | `493690ab5b8dd39ceaf8f67ed90903a937f40c62c4082b0c8adc807eab458d93` | 16.773 / `1e07b434706a2fc4e6da2fd925a5b82ded95681d260163b6d7076c09f8c56eb2` |
| OrcaSlicer | 2.4.2 | `anycubic-kobra-2` | `481c9f071fdb3cda033d1677ce7a9442c41a25cbeeb42cfc808af179b4dc85c3` | 12.006 / `138971d01072cc7448dc68e2b852d31815694042b6300ca66f361ee9ef2f5010` |
| PrusaSlicer | 2.9.6 | `prusa-mk4s` | `7fd50b52d1cc3da87dbcb71e45e764412dd45688bea028f351333e86d9769704` | 54 / `275338fe3acde4a05637e6469b255bddd04f9b9d07eab138d4c64a827a83f6c9` |
| SuperSlicer | 2.5.59.13 | `prusa-mini` | `7bc702f6ff7353ebbc6c5b4c1917970e52de371f3e704f634d9141cca0970c6a` | 23 / `c1390e07319071e0bfc5e384b1fb81e1df397a612fd37dcd4e27a1b04dc8c5f8` |

Cura 5.13.0 ist durch die installierte Produktversion belegt; die gehashte
`CuraEngine.exe` trägt intern die Dateiversion 1.0. Crealitys Registryversion
ist 7.3.0, die ausführbare Datei trägt 6149. OrcaSlicer meldet keine
Dateiversion; 2.4.2 stammt aus den installierten Produktmetadaten.

## Fehlerstand der 52 vollständigen Modelle

| Slicer | Keine Druckdatei | Absturz | Bauraum | Höhe | Fehler gesamt |
|---|---:|---:|---:|---:|---:|
| Bambu Studio | 6 | 0 | 0 | 0 | 6 |
| Creality Print | 4 | 0 | 5 | 0 | 9 |
| Cura | 12 | 0 | 0 | 0 | 12 |
| ElegooSlicer | 11 | 0 | 0 | 0 | 11 |
| OrcaSlicer | 6 | 0 | 3 | 0 | 9 |
| PrusaSlicer | 6 | 0 | 9 | 2 | 17 |
| SuperSlicer | 11 | 17 | 0 | 0 | 28 |
| **Gesamt** | **56** | **17** | **17** | **2** | **92** |

Die fehlgeschlagenen Varianten betreffen folgende Modelle; die Zahlen sind
Varianten, nicht verschiedene Dateien:

- **Keine Druckdatei (56):** `Cat_2.stp` (3),
  `grenuttags_hallare_modell_41x47_curved.stl` (3), beide
  `kumiko_elongated-hexagon_desk-organizer_w150`-Varianten A und B (je 15),
  `large-screwdriver-holder-with-honeycomb-pattern.stl` (12),
  `obj_4_Bayrak Direği uzun.stl` (2), `obj_6_Bayrak Direği.stl` (2),
  `pegboard-goot-ceramic-screwdrivers-v3.3mf` und `.step` (je 1),
  `宠物便便器.3mf` (2). Bei den sechs Bambu-Studio-Fällen meldet `result.json`
  den Rückgabecode `-3` und
  „The input files to the slicer are not found“, obwohl die jeweilige
  übergebene 3MF-Datei vorhanden ist. Der Widerspruch ist ungeklärt. Für die
  übrigen 50 Fälle gibt es keine passende `result.json`; ihre Ursache bleibt
  offen.
- **Absturz (17):** alle von SuperSlicer 2.5.59.13 gemeldet:
  `1x1-bin.stl` (1), `Blessed+Family+–+Heart+Script+Decor.3mf` (6),
  `bromyde_press.3mf` (3), `drill-holder.3mf` (2),
  `pegboard-10inch-crimper-v5.3mf` und `.step` (je 1),
  `screwdriver-holder-hex.stl` (2), `宠物便便器.3mf` (1).
- **Bauraum (17):** `Blessed+Family+–+Heart+Script+Decor.3mf` (12),
  `carpet-corner-clip.step` (3),
  `large-screwdriver-holder-with-honeycomb-pattern.stl` (2). Die zwölf ersten
  Ablehnungen verteilen sich auf Creality (3), Orca (3) und Prusa (6); die
  übrigen auf Prusa (3) und Creality (2).
- **Höhe (2):** `宠物便便器.3mf`, beide auf PrusaSlicer.

Die 50 Fälle ohne passende `result.json` werden nach dem vollständigen Lauf
gegen ihre Prozessdetails geprüft. Bei den 17 Abstürzen ist die Ursache
ebenfalls nicht für alle Dateien belegt. Eine genaue Gegenprobe ist für
`1x1-bin.stl` vorhanden: SuperSlicer 2.5.59.13 endete mit
`3221225477` (`0xC0000005`, Zugriffsverletzung) nach 1,117 s. Windows meldete
`Slic3r.dll+0x1f543e`; wegen fehlender passender PDB lässt sich weder Funktion
noch Auslöser sicher benennen. Wiederholte Fehler an derselben Stelle belegen
keinen gemeinsamen Modellfehler.

## Zweifarbige Testplatte in Creality Print

Die Testplatte hat SHA-256
`ca8efa2477916c46379dc45c302369fef3fd0f6f95749cd92840735eb38ccb03` und ist
nicht Teil der 125 Matrixeingaben. Der Versionsvergleich verwendete denselben
3MF-Inhalt mit Creality Print 7.2.2.5483 und 7.3.0.6149. Beide Projekte
enthielten 100 Werkzeugwechsel und je 119 s für
`machine_load_filament_time`; die Projektmetadaten waren bis auf
`different_settings_to_system` gleich.

| Messwert | 7.2.2.5483 | 7.3.0.6149 |
|---|---:|---:|
| `M73 P0 R` | 33 min | 254 min |
| größtes `TIME_ELAPSED` | 1.991,803 s | 15.244,931 s |
| Kopfzeit | 3 h 51 min 30 s | 7 h 32 min 23 s |
| G0/G1-Befehle | 22.233 | 24.920 |
| Züge mit positiver E-Menge | 14.299 | 17.773 |
| Werkzeugwechsel | 100 | 100 |

Ein kontrollierter 7.3-Lauf variierte nur die zwei Zeitfelder in
`project_settings.config`:

| Maschinenladezeit / Spülzeit | `M73 P0 R` | `TIME_ELAPSED` | Kopfzeit | G0/G1 / positive E-Züge |
|---|---:|---:|---:|---:|
| 119 / 119 s | 254 min | 15.249,173 s | 7 h 32 min 27 s | 24.670 / 17.773 |
| 0 / 119 s | 55 min | 3.349,173 s | 4 h 14 min 7 s | 24.670 / 17.773 |
| 119 / 0 s | 228 min | 13.690,275 s | 3 h 48 min 8 s | 21.532 / 14.049 |
| 0 / 0 s | 55 min | 3.349,173 s | 55 min 47 s | 24.670 / 17.773 |

Der Vergleich 119/119 mit 0/119 hält Werkzeugweg und Extrusion gleich. Allein
`machine_load_filament_time` addiert in diesem Kontrollpaar exakt 11.900 s zu
`TIME_ELAPSED`: 100 Wechsel × 119 s. `M73 P0 R` steigt dabei von 55 auf
254 min; diese ganzzahligen Minuten sind gerundet und entsprechen nicht exakt
11.900 s. Im ursprünglichen Versionsvergleich steigt `TIME_ELAPSED` um
13.253,128 s. Der isolierte Ladezeitanteil aus dem Kontrollpaar entspricht
89,8 % davon; die restlichen 1.353,128 s sind damit noch nicht erklärt.
`creality_flush_time` erhöht im Vergleich 0/119 zu 0/0 die Kopfzeit ebenfalls
um 11.900 s, aber nicht `TIME_ELAPSED`.

Der verbliebene Versionsunterschied ist noch nicht vollständig zugeordnet.
Eine Bewegungszeit-Näherung vergleicht den historischen 7.2.2-G-Code mit dem
kontrollierten 7.3-Lauf 0/119. Sie schätzt rund 1.366 s Mehrzeit am Prime Tower
und rund 4 s bei den übrigen Zügen. Die verglichenen G-Codes stammen jedoch
nicht aus einem identischen Profil: Zwischen dem historischen 7.3-Ergebnis und
dem Kontrolllauf unterscheiden sich unter anderem `printer_settings_id`,
`wipe_tower_x/y` und Filament-/Kompatibilitätsangaben. Die Näherung ist deshalb
ein Hinweis auf den längeren, stärker segmentierten Prime-Tower-Weg, aber keine
vollständige kausale Zerlegung des historischen Versionssprungs. Sie bildet
auch das interne Zeitmodell nicht nach; der Anteil von Beschleunigung und
Zeitmodell bleibt ungeklärt. Die alte 7.2.2-Binärdatei ist nicht mehr
installiert, und eine tatsächliche Druckdauer wurde nicht gemessen.

## Ergänzende lokale Rohbelege

Der versionierte Bericht enthält die gemessenen Werte, Berechnungen und
Ergebnisgrenzen selbst. Die folgenden Rohbelege sind ergänzend und liegen nur
im ignorierten lokalen Prüfverzeichnis; sie sind keine Voraussetzung, um die
Schlussfolgerungen aus diesem Bericht nachzuvollziehen:

- Matrixlauf: `output/review/uebergabe-matrix-2026-10-02-main-129f8ca11-modelle-rerun-02/.matrix-identity` und `treiber.log`.
- SuperSlicer-Gegenprobe: `output/review/oneoff-slicer-capture-rm311-1x1-bin-2026-10-02/slicer-prozess.json`.
- Historische Creality-Ausgaben: `output/review/rm164-2026-09-29/mehrfarbe-creality/` und `mehrfarbe-creality73/`.
- Kontrollläufe mit veränderten Zeitfeldern: `output/review/uebergabe-matrix-2026-09-30/creality-time-control/`.

## Noch offen

- Dieselbe Matrix zu 125 von 125 vollständigen Modelleingaben fortsetzen und
  danach sämtliche Variantenfehler gegen Prozessausgaben und Slicerantworten
  einordnen. Der hier eingefrorene 07:51-Stand ist ein geprüfter Zwischenstand,
  nicht der aktuelle Laufstand; erst die vollständige Matrix schließt den
  Bericht ab.
- Den SuperSlicer-Auslöser ohne passende Symbole nicht als geklärt ausgeben.
- Die fehlenden Druckdateien einzeln klassifizieren; eine fehlende Datei allein
  belegt noch keinen Slicerabsturz.
- Für die Creality-Schätzung bleibt offen, ob die 7.3-Zeit der realen
  Druckdauer näher kommt; das ist mit einem tatsächlichen Druck zu belegen.
