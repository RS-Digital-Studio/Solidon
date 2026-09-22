# P1.4c – kleinster sicherer Einführungsschritt an der Auswertungsgrenze

## Entscheidung

**Ja: native Merkmalsgruppen sind vor einer neuen Kantenpersistenz integrierbar.**
Die registrierten Flächen-/Merkmalsfelder (`feature`, `features`, Skizzenebene,
Passungsseiten) sind ein anderer Referenzweg als `edge_keys` mit Art `edges`.
Die vorhandene Kantenprüfung kann dabei unverändert mehrdeutige oder unvollständige
Schlüsselbündel anhalten. Eine neue Kantenfrage ist keine Voraussetzung für die
Freigabe einer korrekt transportierten Flächenauswahl.

**Nein: eine neue Gruppenfrage allein macht native Flächenverbraucher nicht sicher.**
`push_face` und `_exact_fillet` wählen ihre native Fläche derzeit nach Mitte/
Richtung bzw. Mitte/Radius erneut. Eine ausdrücklich bestätigte Auswahl muss bei
solchen Verbrauchern direkt in deren private Kernelkopie gelangen. Dieser enge
Flächenanschluss ist Voraussetzung für ausführbare native Merkmals-Neuwahl; er
ist unabhängig von der späteren Kanten-UI.

Der kleinste vorherige Einführungsschritt ist daher **Validierung mit sicherem
Halt**, einschließlich belegter bestehender Fortführungen und Schutz gegen die
bloße Namensexistenz in `orphans`. Er führt noch keine neue Antwortdomäne und
keine neue UI-Kantenpersistenz ein. Ein solcher Schritt ist als Prüfsperre
abgeschlossen, nicht als bedienbare native Neuwahl oder allgemeine Topologiehistorie.

Lesende Notiz während des Root-Tors. Keine Produktdatei, Testdatei oder ROADMAP
geändert; keine neuen Tests oder Sonden ausgeführt.

## 1. Welche Fälle welche Behandlung brauchen

| Tatsächlicher Fall | Belegbare Behandlung im ersten Schritt |
|---|---|
| Unveränderter aktueller Körper samt belegter Merkmalsübernahme | Weiterlaufen. Objekt-/Merkmalsidentität nur innerhalb dieses nachgewiesenen Durchreichwegs; bloß gleicher Name oder gleiche Werte genügt bei einer neu aufgebauten Shape nicht. |
| Tatsächliche Transformation | Den vorhandenen Ergebnistransport `OpResult.transform` und die bereits geprüfte aktuelle Flächen-/Kopierabbildung benutzen. `geom/transform.apply` führt vollständige Merkmalsdreiecke über `transformed_with_faces` nach. Keine zweite Transformation und keine alte Dreieckliste am neuen Solid. |
| Eindeutiger geometrischer Match unter demselben logischen Namen | Darf im bestehenden geometrischen Identitätsvertrag nur nach vollständiger Vergleichbarkeit, fehlendem Anspruchskonflikt und gültiger aktueller Auswahl weiterlaufen. Das ist geometrische Zuordnung, keine behauptete OCCT-Historie. |
| Eindeutiger Match zu einem **anderen** aktuellen Namen | Die alte Referenz ist damit nicht automatisch gültig. Im reinen Validierungsschritt anhalten; erst ein späterer kontrollierter Alias-/Neuwahlanschluss darf den logischen Namen am ausgewählten aktuellen Feature publizieren. |
| Verlorenes altes Merkmal | Ein aktiver benötigter Verweis hält an. Ein zufällig neu vergebenes gleichlautendes Merkmal heilt den Verlust nicht. Kein leerer Parameter, Ursprung oder ganzer Körper als Ersatz. Nicht mehr benötigte frühere Referenzen dürfen den späteren Schritt dagegen nicht sperren. |
| Ungeprüftes Merkmal | Unbekannt, nicht gültig. Fehlende aktuelle Lage, nichtendliche Werte, leere/fremde Dreiecke, fehlende native Zuordnung oder ausgelassene Prüfung liefern keine Freigabe. Die Abwesenheit einer negativen Meldung ist kein Positivbeleg. |
| Gleichlautender neu nummerierter Name | `face_1` kann nach `features_of` eine andere Fläche sein. `matched.orphaned` oder `matched.ambiguous` hat Vorrang vor `name in features`; auch bei nur einem umkämpften Nachfolger. Namen werden nicht als native Indizes gelesen. |
| Mehrere alte Ansprüche | Keine Freigabe durch globale Solver-Paarung, erste Quelle, `created_by`, gleiche Slots oder `provenance`. Der P1.4b-Gruppenschluss bleibt maßgeblich. Im Einführungsschritt Halt, noch keine automatische native Wiederwahl aus Netzantworten. |
| Absichtlich fortgeführter `resize_hole`-Alias | Den Beleg aus `_preserved_exact_features` erhalten und vor einem neuen Vergleich mit den **alten** Maßen anwenden. Die bewusst geänderte Bohrung wird gegen das Zielmaß wiedergefunden; der Boden hat seinen eigenen geometrischen Beleg. Große gewünschte Maßsprünge dürfen dadurch nicht wieder verwaisen. |
| Neu eingeführtes, bislang nicht referenziertes Merkmal | Keine alte Identität behaupten. Eine fehlende Fortführung allein ist kein Grund, eine ansonsten gültige freie Geometrie zu blockieren. Die neue aktuelle Auswahl bleibt tatsächlich neu. |

### Zwei konkrete Schranken des aktuellen Codes

`evaluate._with_features` führt den nativen Match aktuell nur bei
`touches_features` und unter `FEATURE_LIMIT_COUNT` aus und sperrt dort nur die
referenzierte Mehrdeutigkeit. `push_face` und `draft_faces` setzen das Flag nicht,
obwohl sie native Geometrie ändern und `features_of` erneut ausführen. Das Flag
beschreibt das Einführen von Merkmalen und ist **kein** Beleg für erhaltene
Referenzen. Es darf bei der neuen Prüfung nicht als Gültigkeitsweiche dienen.

`orphans._resolves` prüft ausschließlich die Existenz des Namens, bei leeren
Objektkennungen sogar an irgendeinem Körper. Es kann weder eine verworfene alte
Identität noch eine ungeprüfte gleichlautende neue Fläche erkennen. Die neue
Auswertungsgrenze muss diesen fehlenden Zustand ausdrücklich transportieren;
eine weitere Namenssuche löst das Problem nicht.

## 2. Bestehende absichtliche Aliasfortführung nicht erraten

`geom/prepare_ops.py:_preserved_exact_features` besitzt heute bereits den nötigen
engen fachlichen Beleg:

1. `_expected_bore` beschreibt die bewusst geänderte Bohrung mit dem neuen Maß.
2. `_bore_match_id` sucht ihren tatsächlichen eindeutigen aktuellen Nachfolger.
3. `_resized_bore_floor` belegt gegebenenfalls den veränderten Boden über echte
   Ränder und die gemeinsame Ebene.
4. `match` und `apply_mapping` veröffentlichen aktuelle Merkmale unter den
   fortgeführten logischen Namen.

Der allgemeine Auswerter bekommt hiervon bislang lediglich das neue
`SceneObject.features`. Er sieht nicht, welcher Alias mit einer solchen
Änderungsabsicht belegt wurde. Weder `provenance`, gleicher Name, gleiches
`created_by` noch eine Fallunterscheidung allein nach `operation.op == resize_hole`
sind ein ausreichender Ersatz.

**Deshalb ist ein sauberer erster Schritt nicht ausschließlich in evaluate/orphans
möglich**, wenn bestehende gewollte Aliasfortführungen unverändert erhalten bleiben
sollen. Er braucht einen kleinen Ergebnistransport aus dem bestehenden Produzenten.
Keine neue Nachberechnung der Bohrungsabsicht im Auswerter und keine zweite Formel.

## 3. Schmaler Ergebnistransport, keine Projektpersistenz

Vorschlag für die Grenze vor Umsetzung; noch keine bestehende API:

```python
@dataclass(frozen=True, slots=True)
class FeatureContinuation:
    source: FeatureRef
    target: FeatureId

# OpResult: je Ausgabe eine unveränderliche Folge tatsächlicher Belege.
# Die Ausgabe ist über ihre Position zugeordnet, da sie ihre endgültige
# Objektkennung erst beim Einhängen erhält.
feature_continuations: tuple[tuple[FeatureContinuation, ...], ...] = ()
```

Das Feld ist eine belegte Ausgabe der konkreten Berechnung, ähnlich dem schon
bestehenden `transform`. `source` ist körperqualifiziert, damit zwei Eingaben mit
`hole_1` nicht kollidieren. `target` bezeichnet ein tatsächlich vorhandenes
Merkmal **der zugehörigen aktuellen Ausgabe**, auch wenn diese dessen Alias
bereits trägt. Es ist kein nativer Index und kein weiterer dauerhafter Namensdienst.

Der Produzent meldet nur tatsächlich veröffentlichte eindeutige Paare. Wenn
`_bore_match_id` einen Kandidaten sieht, der spätere gemeinsame Anspruchsschluss
aber keine Fortführung freigibt, reicht der erste Fund nicht zum Ausstellen eines
Belegs. Beim Boden gilt dieselbe Bedingung. Der Beleg darf nicht nachträglich aus
dem vollständigen Output-Namenssatz oder einem Wahrheitsflag abgeleitet werden.

Die allgemeine Grenze prüft Struktur und Bezug: Quelle gehört zu den tatsächlichen
Eingängen, Quelle war dort bekannt, Ziel existiert an der richtigen Ausgabe,
Doppelziele fehlen, aktuelle Auswahl ist gültig. Die fachliche Änderungsabsicht
entsteht ausschließlich am bestehenden Geometrieprüfer, nicht an dieser Struktur-
prüfung. Ein echter Nachweis kann eine Form-/Größenänderung erklären; er macht
nicht pauschal andere gleichnamige Ausgabemerkmale vertrauenswürdig.

### Rohcache ist zwingender Teil dieses ersten Schritts

`OpResult` wird in `CachedResult` überführt, bevor die allgemeine Nachzuordnung
läuft. Das neue Belegtupel muss deshalb denselben Weg vollständig durchlaufen:

- kalte Ausgabe → `CachedResult` → warmer Treffer;
- Diskcodec → neue Prozess-/Cacheinstanz → wiederhergestellter Rohoutput;
- mehrfache Ausgaben mit klarer ordinaler Zugehörigkeit;
- vorhandene `transform`-Auskunft und Abbruchgrenzen gemeinsam erhalten.

Kein Cachetreffer darf den Aliasbeleg verlieren oder aus alten gecachten Namen
neu erfinden. Fehlendes Feld alter Caches bedeutet unbekannter alter Stand;
Cacheformat erhöhen und neu rechnen. Eine aktuelle leere Belegfolge bedeutet
nur „kein zusätzlicher absichtlicher Fortführungsbeleg“. Sie sagt nichts über
geometrische Matchbarkeit oder Verlust aus.

**Keine Projektformatmigration für dieses Feld:** Es ist ein abgeleitetes
Operationsergebnis. Die Projektdatei behält Parameter/Quellen und rekonstruiert
den Beleg beim Rechnen. Die separate native Antwortdomäne bleibt Aufgabe des
späteren Persistenzpakets; diese Notiz greift policy_review nicht vor.

## 4. Auswertungsgrenze und Orphans

Die neue Gültigkeitsprüfung braucht für den nativen Übergang die wirklichen
Quellobjekte, nicht nur `previous: dict[FeatureId, Feature]` und deren Hüllquader.
Nur so kann sie aktuellen Körper, nachgewiesenes Durchreichen und native
Kopier-/Transformationsauskunft auseinanderhalten. `inputs` und `previous_features`
liegen im Auswerter bereits vor; sie werden gezielt bis zur Grenze weitergereicht.

Ein möglicher reiner Helfervertrag:

```python
def validate_native_references(
    previous: SceneObject,
    current: SceneObject,
    referenced: Collection[FeatureId],
    *,
    matched: MatchResult | None,
    continuations: Sequence[FeatureContinuation] = (),
    check_cancelled: Callable[[], None] | None = None,
) -> frozenset[FeatureId]: ...  # Nicht sicher aufgelöste alte Referenzen.
```

`matched=None` heißt ungeprüft, nicht alle gültig. Der Helfer führt keine neue
Matchrechnung aus, überschreibt keine Namen und beantwortet keine Frage. Einen
reinen Transformationsbeleg bereitet der vorhandene Transformationsweg vor;
`transform != None` allein darf nicht eine unpassende Teilflächenübernahme freigeben.
Ein anfänglich erzeugter Körper ohne alten Referenzbestand braucht keine erfundene
Vorgängerzuordnung.

Die Native-Prüfung läuft nach jedem betroffenen aktuellen Ausgabeübergang, auch
nach Cachetreffern und unabhängig von `touches_features`. Bekannte Durchreich-/
Transformationsbelege erlauben den kurzen Weg. Ohne solche Belege wird für
benötigte alte Referenzen geprüft oder ausdrücklich angehalten; eine Budget- oder
Merkmalsgrenze lässt die Prüfung nicht still verschwinden.

Für die erste Sperrstufe ist der vorhandene atomare Halt an der **Erzeugergrenze**
der kleinste Anschluss: keine teilweise Veröffentlichung ihrer Ausgaben, Antworten
oder Folgewirkungen. Der Befund nennt zusätzlich den tatsächlich betroffenen
späteren Verweis/Verbraucher, damit der Grund nicht mit einem ungültigen Parameter
der gerade erzeugenden Operation verwechselt wird.

Der gesperrte Referenzzustand muss strukturiert zum nachgeschalteten Orphan-Check
kommen. Schmaler Vorschlag: `EvaluationResult.blocked_references` als abgeleitete
körperqualifizierte Menge mit Standardwert leer und ein entsprechendes optionales
Argument an `orphans.check`. Die einzige Session-Weitergabe ist Infrastruktur,
keine neue Auswahloberfläche. Für diese Menge darf `_resolves` nicht allein wegen
eines vorhandenen Namens Erfolg melden. `orphans.check` darf sie aber auch nicht
an der alten, vor dem angehaltenen Erzeuger liegenden Szene erneut auswählen oder
sequenziell in scheinbar gültige Einzelantworten umschreiben. Die Sperre bleibt
mit ihrem Handlungsweg erhalten, bis der native Neuwahlanschluss sie beantwortet.

Damit ist die Unvollständigkeit des ersten Schritts ehrlich: Er sperrt unsichere
Referenzen, bietet aber noch keinen neuen atomaren nativen Reparaturdialog an.
Eine Meldung darf deshalb nicht behaupten, bloßes erneutes Wählen derselben alten
Kennung heile den Zustand bereits. Vorhandene bewusste Bearbeitungswege am
betroffenen Schritt bleiben erhalten.

### Referenzlebensdauer beachten

`referenced_features` wird heute einmal über das gesamte Dokument erhoben.
Eine neue strengere Prüfung darf diese Menge nicht ungeprüft als „alle noch
benötigt“ behandeln: Ein in Schritt 2 benutzter und in Schritt 3 absichtlich
entfernter Bezug sperrt Schritt 3 nicht allein wegen seiner früheren Verwendung.
`orphans.pending_references` enthält bereits den zeitlichen Vertrag: vor einem
angehaltenen Verbraucher dessen Eingänge, im Endstand aktive Passungen.

Für die Erzeugerprüfung werden nur danach noch ausgeführte Verbraucher und aktive
Endpassungen betrachtet, entlang tatsächlicher Objektweitergabe. Der bestehende
Registerscanner bleibt die Quelle für Referenzen. Bei Aufteilung/mehreren Körpern
darf ein gleicher Feature-Name nicht über beliebige Ausgaben hinweg gelten.
Aktuelle neu angelegte Referenzen ohne gespeicherten Herkunftsbeleg können in
dieser ersten konservativen Stufe noch Klärung benötigen; das ist keine
Entschuldigung für eine Namensexistenzfreigabe.

## 5. Warum Flächengruppen und Kanten unabhängig bleiben

Nach dieser Sperrstufe kann ein eigenes, vollständig abgeschlossenes Paket native
**Merkmalsgruppen** freigeben, wenn es zusätzlich Folgendes einlöst:

- vollständige native Gruppen-/Scopeprüfung aus der abgestimmten Persistenzquelle;
- aktuelle Zielmerkmale und gültige native Auswahl, gemeinsame Injektivität;
- direkte private Flächenauswahl für `push_face` und `unround/reround`, sodass
  Normalen/Mitte/Radius nicht nochmals eine andere Fläche aussuchen;
- vorhandener körperqualifizierter Frage-Zwischenkörper und atomare Antworten;
- fortgesetzte Reservierung verworfener Namen und korrigierter Bindungsdigest
  im Folgecache;
- ehrliche offene Behandlung von Nichtfortführung und ungültiger Vollflächenwahl.

Die Kantenwege bleiben dabei bei ihrem heutigen vollständigen Schlüsselvertrag:
`named_edges/wanted` lehnt Kollisionen und fehlende Teilauswahlen ab. Sie dürfen
native Merkmalsgruppen weder konsumieren noch dadurch freigegeben werden. Sobald
Kanten selbst neu gewählt und gespeichert werden sollen, kommt ihr eigener
Token-/Auswahltransport hinzu. Beide Themen gemeinsam zu implementieren ist für
die Consumersicherheit **nicht** zwingend; Flächenwahl ohne sichere Flächen-
Consumerschnittstelle wäre dagegen unvollständig.

## 6. Dateien und spätere Abnahmekriterien des Einführungsschritts

Kernänderungen nach dem Tor: `scene/evaluate.py`, `scene/orphans.py`, der kleine
Ergebnisvertrag in `types.py`, `CachedResult`/Diskcodec in `scene/cache.py` sowie
Ausstellen der konkreten Belege im bestehenden `_preserved_exact_features`-
Produzentenpfad. Dazu die minimale Weitergabe zum Orphan-Check in `ui/session.py`
und zugehörige Bereichskarten. Keine neue Antwortpersistenz, kein neuer Kanten-
dialog, keine neue allgemeine native Historienbibliothek.

Spätere unabhängige Kernfälle – hier **nicht** ausgeführt:

1. Verlorenes natives `face_1` mit gleichlautendem neuen Fremdmerkmal stoppt den
   benötigten Folgeverweis; Orphans meldet wegen Namensexistenz keinen Erfolg.
2. Neuerkennung nach `push_face`/`draft_faces` wird trotz fehlendem
   `touches_features` geprüft. Ein unveränderter Durchreichweg bleibt frei.
3. Ungeprüfter/ungültiger Kandidat oder ausgelassener Match bleibt unbekannt.
   Frischer gleichlautender Name, `generated`, `created_by` und gleiche
   Filamentwerte ändern daran nichts.
4. Eindeutiger neu nummerierter Partner darf ohne kontrollierte Aliasübernahme
   keinen Verweis auf den alten Namen freigeben.
5. Bewusste große Durchmesseränderung durch `resize_hole` erhält ihre tatsächliche
   Bohrungs-/Bodenfortführung; ein daneben liegendes ähnliches Loch erhält sie
   nicht. Der Erwartungswert stammt aus dem neuen Zielmaß und der echten Lage.
6. Derselbe Aliasfall kalt, warm und aus Diskcache: Ergebnis, Belegtupel und
   Folgeoperation stimmen überein. Alter Cache ohne Beleg wird nicht geglaubt.
7. Zwei Eingangs-/Ausgabekörper mit gleicher alter ID bleiben qualifiziert;
   falsche Quelle, fehlendes Ziel und Doppelziel werden abgewiesen.
8. Nachgewiesene Transformation trägt aktuelle Auswahl genau einmal mit;
   unvollständige Teilflächenübernahme wird nicht durch die Matrix legitimiert.
9. Eine nur früher benötigte Referenz sperrt spätere absichtliche Entfernung
   nicht; eine noch benötigte Skizzenebene oder aktive Passung dagegen schon.
10. Abbruch und Fehler nach erster Ausgabe publizieren weder Teilbeleg noch
    Antworten/Folgecache. Die Struktur des blockierten Verweises bleibt
    nachvollziehbar und wird nicht gegen den falschen Vorschauzustand repariert.

Fensterdateien bleiben ausschließlich Release-Nachweis. Die reine Prüfsperre ist
kein Nachweis für neue Flächen-/Kantenbedienung; diese erhalten ihre eigenen
Consumer- und UI-Kriterien in den getrennten Folgepaketen.
