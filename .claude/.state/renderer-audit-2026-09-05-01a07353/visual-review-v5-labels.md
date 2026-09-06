# Sichtprüfung der V5-Beschriftungen und gehaltenen Körperzugvorschau

Nur die sechs vorhandenen PNGs betrachtet; keine Anwendung gestartet und keine
Produktionsdatei geändert. Die Aussage gilt für Peg in genau diesen Bildern.

| Bild relativ zum Auditordner | Sichtbefund |
|---|---|
| `final/vtk/file-09/all-features-before-layers.png` | Die Felder liegen vollständig hinter den Namen. Keine überlappenden oder am Feldrand abgeschnittenen Texte; die Verbindungslinien erreichen die Felder und bleiben außerhalb sichtbar. **P3:** Die geöffnete Analysekarte verdeckt den untersten Körperabschluss um ungefähr zehn Bildpunkte: sichtbare Modellkante an der Kartenoberkante um y855; bei gleicher Ansicht im Themenbild reicht der Abschluss bis etwa y865. |
| `final/vtk/file-09/theme-light.png` | Dunkle Schrift vollständig auf hellem Feld. Die gewählte Verrundung und ihr Marker bleiben erkennbar; die dunkle Verbindung führt zum Feldrand. Keine Zeichenreste oder gegeneinander verschobenen Feld-/Textteile sichtbar. |
| `final/vtk/file-09/theme-dark.png` | Helle Schrift vollständig auf dunklem Feld, Verbindung sichtbar. Kein erneuter horizontaler Feldversatz. |
| `final/vtk/file-09/04-layers-middle.png` | Vier lesbare Namen um die Schnittfläche, keine schwebenden globalen Namen oberhalb des abgeschnittenen Körpers. Verbindungslinien kreuzen sich örtlich über der Schnittfläche, überdecken aber keine Schrift. |
| `gesture-calibration/gfx/file-09/gesture-body-held-preview.png` | Marker und Verbindungen liegen sichtbar am verschobenen orangefarbenen Körper. Kein zurückgebliebener Name am grauen Ursprungsumriss erkennbar. Namen, Ø und Hochzahlen bleiben lesbar. Die Schrift wirkt kräftiger und gröber als im VTK-Bild; daraus allein folgt kein belegter Zeichenfehler. |
| `gesture-calibration/vtk/file-09/gesture-body-held-preview.png` | Marker und Verbindungen liegen ebenfalls am verschobenen Körper. Felder und Texte sind ausgerichtet, die Namen überlappen einander nicht. Der graue Ursprungsumriss trägt keine zurückgebliebenen Labels. |

Ein Einzelbild beweist weder den exakten Weltabstand zwischen Marker und
Merkmal noch den zeitlichen Verlauf ohne Flackern. Der rote Helfercheck
`displayed_anchor_to_text` wird durch diese Sichtprüfung weder bestätigt noch
widerlegt; seine geometrische Erwartung wird separat geprüft. Helle und dunkle
Themen wurden hier für VTK angesehen, die gehaltene Zugvorschau für beide
Renderer nur im dunklen Thema. Aussagen zu anderen Modellen, Kameralagen oder
Skalierungsfaktoren lassen sich daraus nicht ableiten.

Die kleine Überdeckung am Fuß ist zunächst eine Beobachtung bei dieser
Kameralage, kein Auftrag für einen automatischen Kamerasprung beim Öffnen der
Analysekarte. Der anschließende begrenzte Lesetest zeigt: `reset_camera` für
Pos1 berücksichtigt im normalen Körpermodus nur den um feste zwölf Prozent
erweiterten Weltquader. Die gemeldeten `_zone_margins` gehen dort nicht ein;
`occluded_view_shift` wird nur für die Skizzenkamera verwendet. Vor einer
Änderung bleibt nativ zu prüfen, ob ein ausdrückliches Pos1 bei offener Karte
weiterhin einen Körperteil verdeckt. Außerdem enthält der direkte Pos1-Pfad
keinen abschließenden Renderaufruf; auch dessen sichtbare Rückmeldung gehört
in diese noch ausstehende Probe. Es wurden dafür keine Prozesse gestartet.

## Bildidentität

Die Pfade können in späteren Reihen erneut verwendet werden. Gelesene SHA-256:

```text
e27c8e53e642593cd2ca8936b34603e62c51cf3065631cdf47b88b5c3a2825eb  final/vtk/file-09/all-features-before-layers.png
407594f82ce629f2f5bd3eac2ec7092441bb67bee559600c2c14de4090038071  final/vtk/file-09/theme-light.png
0f0bfee62eeb91c842efadef83a83ca2a1032bcbaabe8b02363d99d421f617cd  final/vtk/file-09/theme-dark.png
1e5403718a0a1de937eea60f09c7848876d4da328aa8c3b19c0d9fd2744ab48c  final/vtk/file-09/04-layers-middle.png
f169b15064871b07f8a01c854ac9d828b81508bbd932a994af43d954b32c157d  gesture-calibration/gfx/file-09/gesture-body-held-preview.png
52afa3382369f67f16a02d52264b745b02dde21f9669b95adcae40cd1bd2defa  gesture-calibration/vtk/file-09/gesture-body-held-preview.png
```
