# P1.4c – Reihenfolge nach den drei Anschlussreviews

Grundlage sind `p14c-native-reference-plan.md`,
`p14c-ui-kernel-review.md`, `p14c-persistence-review.md` und
`p14c-evaluation-boundary.md`. Der erste Vorschlag wird nur mit den folgenden
Präzisierungen umgesetzt. P1.4b bleibt bis zu seinem grünen Entwicklungstor
und dem eigenen Commit unverändert; die zwei gefundenen Prüfanschlüsse werden
zuerst abgeschlossen.

## 1. Tatsächliche Vollflächenauswahl

`push_faces` und `unround` nehmen optional eine ausdrückliche aktuelle native
Flächenmenge an. Die bestehenden Durchreich-, Tessellations- und Kopierhelfer
werden wiederverwendet. `None` bezeichnet den bisherigen unbenannten Modus;
eine leere oder ungültige ausdrückliche Auswahl wechselt niemals dorthin.
`face_ops` und der Entfernen-Zweig von `_exact_fillet` geben die ausgewählten
vollständigen Originalflächen weiter. Die Zulässigkeit mehrerer Flächen richtet
sich nach dem tatsächlichen Algorithmus. Keine zusätzliche Auswahloberfläche,
kein neuer Antwortspeicher und keine Projektmigration für diesen Schritt.

Abnahme: reale benachbarte Stufen/Rundungen, nur gewählte Stelle verändert,
vollständige gegenüber teilweiser Trägerabdeckung, private Kopierabbildung,
unveränderte Eingabe nach Erfolg/Fehler/Abbruch, bestehende unbenannte Modi.
Der Radiuswechsel bleibt als Anschluss mit zwei gesonderten Übergängen offen.

## 2. Native Merkmalsfortführung und atomare Neuwahl

Die geprüfte Änderungsabsicht von `resize_hole` kommt aus dessen vorhandenem
geometrischen Nachweis als enges, körper-/ausgabequalifiziertes Ergebnispaar.
Der allgemeine Auswerter errät sie weder anhand des Operationsnamens noch
anhand gleicher Merkmalnamen oder `touches_features`. Der Beleg reist wie
`transform` durch den Rohcache und wird aus den Projektparametern neu erzeugt;
keine zusätzliche Projektpersistenz für abgeleitete Topologieauskunft.

Danach werden benötigte native Bezüge nach jedem tatsächlichen Übergang geprüft.
Die Lebensdauer der Verweise zählt: frühere, bereits verbrauchte Bezüge sperren
eine spätere beabsichtigte Entfernung nicht. Ungeprüfte oder verlorene alte
Identitäten werden durch einen neu vergebenen gleichen Namen nicht gültig.
Der strukturierte Sperrzustand erreicht den Orphan-Anschluss und wird dort
nicht gegen die alte Szene in vermeintlich gültige Einzelantworten aufgelöst.

Die native Gruppenwahl teilt P1.4b-Validierung, Vorschau, Atomizität und
Fingerabdrücke, erhält aber eine eigene native Domäne mit engem Erzeugerscope.
Aktuelle Auswahlfähigkeit und vollständige eindeutige Wiedererkennung bleiben
zusätzlich nötig. Format 28 erhält einen eigenen Schritt 27→28 ohne erfundene
Zustimmungen; der bestehende tiefe Serializer bleibt erhalten. Noch offene
Flächenverbraucher werden vor Freigabe ihres Neuwahlwegs angeschlossen.

## 3. Kantenbindung und Radiuswechsel

Kanten sind ein typisierter Eingangsselektor der Operation. Ein gemeinsamer
Vorbindungsschritt löst registrierte `edges`-Felder vollständig vor dem
Verbrauchercache auf. Verschiedene bestätigte Kanten müssen dessen Schlüssel
unterscheiden. Der vorhandene P1.4b-Ausgabehash ersetzt diese Grenze nicht.

Eindeutig neu gewählte dauerhafte Schlüssel können den bestehenden
Parameterantwortweg benutzen. Echte Schlüsselkollisionen brauchen getrennte
Fragetoken und körper-/feldgebundene Antworten; es wird nicht erneut derselbe
kollidierende Schlüssel im Kernel nachgeschlagen. Ein gemeinsamer äußerer
Fragekanal trägt Merkmals- und Kantenziele. Der rein interne nachgelagerte
`FeatureQuestionContext` muss dafür nicht unnötig umgebaut werden.

Private Kopien übertragen die echte gewählte Kante. Die Defeaturing- und
Fillet-Builder müssen beide Übergänge des Radiuswechsels belegen: gewählte
Rundungsfläche → neue scharfe Kante → neue Rundung. Vorhandene
`Modified`-/`Generated`-Methoden und Filamenthistorie sind allein noch kein
solcher Nachweis. Eine reale Gegenprobe entscheidet den nutzbaren Verlauf;
bei ungeklärtem Übergang wird am tatsächlichen Zwischenkörper neu gewählt.

## 4. Gemeinsamer Lebenslauf und Prüfgrenze

Jede Einheit erhält ihren betroffenen Kern-/Statiknachweis vor der nächsten.
Der Gesamtanschluss umfasst kalten/warmen Cache, neue Plattencacheinstanz,
Save/load, Undo/Redo, Maß-/Kern-/Scopewechsel, mehrere Körper, Gruppenabbruch
und den gemeinsamen Agentenweg. Produktionsgrenze 1000 unverändert.
Fensterdateien und Leistung laufen weiterhin ausschließlich beim Release.
P1.4c bleibt bis zum vollständigen fachlichen Anschluss als Ganzes offen.
