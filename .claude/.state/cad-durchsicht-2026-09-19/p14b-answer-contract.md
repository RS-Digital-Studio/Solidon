# P1.4b — konkreter Speicher- und Fragevertrag

Lesende Vorbereitung vom 20.09.2026. Ergänzt
`p14-competing-identities-plan.md`; keine Produktänderung und kein Testlauf.
Gelesener Stand: Projektformat 26, Cacheformat 19. Die Nummern werden beim
Umsetzen gegen den dann aktuellen Stand geprüft.

## 1. Kleinste tragfähige Erweiterung

Antworten bleiben ausschließlich in `Operation.matches`. Eine vollständig
entschiedene Konkurrenzgruppe ist **ein** Eintrag, der Körper und sämtliche
alten Ansprüche bezeichnet. Der Eintrag enthält den ganzen damaligen
Kandidatengraphen und für jeden alten Anspruch entweder den gewählten
geometrischen Fingerabdruck oder eine ausdrückliche Nichtfortführung.
Fingerabdrücke werden in einer Tabelle einmal gespeichert; Entscheidungen
verweisen innerhalb desselben Eintrags auf deren Index. Neue Erkennungs-IDs
werden nicht gespeichert.

Auch eine gewöhnliche Frage mit einem alten Anspruch kann als Gruppe mit
einem Element gespeichert werden. Damit brauchen neue Antworten keinen
zweiten Einzelantwortweg. Alte Einzelantworten bleiben lesbar, dürfen aber
keine erst jetzt erkannte Konkurrenzgruppe freigeben.

Die Frage bleibt `ask(question, choices) -> str`. Pro altem Anspruch werden
die aktuellen neuen Kandidaten gezeigt. Der Text nennt Körper, alten Bezug,
konkurrierende alte Ansprüche und die Folge einer Nichtfortführung. Keine
neue Oberfläche für Permutationen und kein weiterer Antwortcache.

## 2. Tatsächliche Anschlussstellen und bisherige Lücken

- `types.Operation.matches:1641` ist heute
  `Mapping[FeatureId, Mapping[str, Any]]`. `serialise.operation_to_data:522`
  und `operation_from_data:548` kopieren die äußeren Wörterbücher; verschachtelte
  JSON-Werte können bereits reisen. Der neue Schlüssel bezeichnet eine
  Antwortgruppe, also künftig `Mapping[str, Mapping[str, Any]]` samt Vertrag.
- `project._validate_operation_schema:872` prüft bei `matches` bisher nur
  Wörterbuch und Wörterbuchwerte. Neue Gruppeneinträge brauchen eine eigene
  Strukturprüfung; Geometrie wird beim Laden nicht gerechnet.
- `History.record_matches:895` vereinigt äußere Einträge und ersetzt die
  Operation ohne zusätzliche Transaktion. Genau diese Ebene eignet sich für
  ganze Gruppen. Kein rekursives Zusammenführen einzelner Entscheidungen.
  `_swap_operation:1220` hält aber getrennte Fassungen in
  `changes.before/after.edited_ops`; `redo:1425` setzt deren gespeicherte
  `after`-Fassung wieder ein. Eine nach der Parameteränderung beantwortete
  Frage aktualisiert diese Fassung bisher nicht. Das ist eine vorhandene
  Anschlusslücke, keine bereits belegte Undo-/Redo-Erhaltung der Antwort.
- `_with_features:1820` liest bisher `saved.get(old_id)` und ergänzt nach
  jeder Antwort `matched.mapping` und `recorded`. Die Ausgabeschleife bei
  `evaluate:640` übernimmt `recorded` bereits nach jedem Ausgabekörper,
  obwohl ein späterer Körper derselben Operation noch anhalten kann.
- `Session._on_finished:3196` schreibt `result.matches` über die History,
  setzt bei Änderung den vorhandenen Dirty-Zustand und startet keinen
  zusätzlichen Lauf. Das bleibt der einzige Veröffentlichungsweg.
- `Session.announce_candidates:3146`, `ask_from_worker:3169` und
  `AskRequest.preview/candidates` besitzen bereits den richtigen Kanal.
  Der nachgelagerte Waisencheck setzt `_pending.preview`; die eigentliche
  Merkmalszuordnung liefert bisher keine Vorschau ihres neuen Zwischenkörpers.
- `MainWindow._on_ask:16820` löst Kandidaten gegen die gezeigte Szene auf.
  Seine bisherige Vorschau benutzt `_on_scene`, also den vollständigen
  Ergebnisweg einschließlich Baum, Bericht, Verlauf und Sichtbarkeitszustand.
  Das ist für eine noch ungeklärte Operationsausgabe zu weitgehend.
- `Viewport.show_scene:5527` kann asynchron vorbereiten. Direkt danach ist
  die neue Geometrie noch nicht zwingend sichtbar; `is_scene_applied` und
  `sceneApplied` sind die vorhandenen Nachweise für die tatsächliche Anzeige.

## 3. Konkretes JSON-Format

Alle aktuellen Gruppen liegen als eigene äußere Einträge unter `matches`.
Der einzige reservierte andere Schlüssel ist `legacy`. Das vermeidet eine
Kollision mit beliebigen historischen Feature-Namen: In Format 27 liegen
alle alten Namen innerhalb von `legacy`, auch ein alter Name `legacy` oder
ein Name, der zufällig wie ein Gruppenschlüssel aussieht.

Der Gruppenschlüssel lautet:

```python
"group:" + json.dumps(
    [object_id, sorted(old_ids)], ensure_ascii=False, separators=(",", ":")
)
```

Keine Trennzeichenverkettung ohne Escaping, kein Hash mit zusätzlichem
Kollisionsvertrag. `object_id` ist die tatsächliche Ausgabe-ID der Operation,
nicht ihr übersetzter Name. Die Operations-ID steht bereits eine Ebene höher.

Beispiel eines vollständigen Operationseintrags:

```json
{
  "id": 7,
  "op": "thicken",
  "in": ["obj_1"],
  "out": ["obj_1"],
  "params": {},
  "matches": {
    "legacy": {
      "pin_9": {
        "kind": "hole",
        "relative": [0.1, 0.0, 0.0],
        "axis": [0.0, 0.0, 1.0],
        "diameter": 4.0,
        "directional": false
      }
    },
    "group:[\"obj_1\",[\"pin_1\",\"pin_2\"]]": {
      "object_id": "obj_1",
      "old_ids": ["pin_1", "pin_2"],
      "candidates": [
        {
          "fingerprint": {
            "kind": "hole",
            "relative": [0.25, 0.0, 0.0],
            "axis": [0.0, 0.0, 1.0],
            "diameter": 4.0,
            "directional": false
          },
          "claims": ["pin_1", "pin_2"]
        }
      ],
      "decisions": {
        "pin_1": {"candidate": 0},
        "pin_2": {"not_carried": true}
      }
    }
  }
}
```

`candidate: 0` bezeichnet den Fingerabdruck der lokalen Tabellenzeile, keine
aktuelle oder zukünftige Feature-ID. `not_carried: true` bedeutet ausdrücklich:
Der alte Name wird durch diese Zuordnung nicht fortgeführt. Weder Geometrie
noch spätere Operationen oder Passungen werden dadurch gelöscht. Ein späterer
Verweis darf deshalb weiterhin einen echten Waisenbefund auslösen.

Der bestehende Fingerabdruckvertrag bleibt unverändert: Nur `relative` wird
in `feature_vector` durch die Modelldiagonale normiert. `vector[6]` und damit
das historisch benannte Fingerabdruckfeld `diameter` übernehmen das Rohmaß
aus `params.diameter`, ersatzweise `params.area`. Bei einem Durchmesser sind
das Millimeter, bei einer Fläche Quadratmillimeter; im Beispiel beträgt der
wirkliche Durchmesser 4 mm. Das Feld erhält weder eine neue Normierung noch
eine Umrechnung. Achse, gerichtete Normale, Rundung und Annahmeschwellen
bleiben bei `fingerprint/resolve`. Keine neue Maßunsicherheit.

### Strukturelles Schema und Integritätsregeln

```text
Matches := {
  "legacy"?: { FeatureId: LegacyFingerprint },
  GroupKey*: Group
}
Group := {
  "object_id": ObjectId,
  "old_ids": nonempty unique sorted FeatureId[],
  "candidates": nonempty Candidate[],
  "decisions": { every old_id exactly once: Decision }
}
Candidate := {
  "fingerprint": Fingerprint,
  "claims": nonempty unique sorted FeatureId[]
}
Decision := { "candidate": nonnegative integer }
          | { "not_carried": true }
Fingerprint := {
  "kind": string,
  "relative": [finite number, finite number, finite number],
  "axis": [finite number, finite number, finite number],
  "diameter": finite number,
  "directional": boolean
}
```

Zusätzlich zwingend: Schlüssel passt exakt zu `object_id/old_ids`;
`object_id` gehört zu den Ausgaben dieser gespeicherten Operation;
`claims` sind Teilmengen von `old_ids`, ihre Vereinigung ist `old_ids`;
ein Entscheidungsindex liegt in der Tabelle und seine Zeile beansprucht
diese alte ID; kein Index ist zweimal gewählt. Boolesche Werte sind keine
Indizes oder Zahlen. Beide Entscheidungsformen sind exklusiv; fehlende
Entscheidungen, `false`, zusätzliche Entscheidungsschlüssel oder unbekannte
Gruppenfelder sind ungültig. Die vorhandenen JSON-Tiefen-, Größen- und
Endlichkeitsgrenzen bleiben zuständig; keine eigene zweite Budgetverwaltung.

Historische Fingerabdrücke werden beim Migrieren nicht ergänzt oder
umgerechnet. Strukturell unbrauchbare Altwerte dürfen lesbar bleiben, aber
keinen geometrischen Beleg liefern. Vor `resolve` insbesondere Form und
Endlichkeit der tatsächlich verwendeten Vektoren prüfen; fehlende Lage nicht
als Ursprung erfinden. Die bekannten historischen optionalen Felder folgen
ihrem vorhandenen Vertrag. Neue Gruppen schreiben immer vollständige Werte.

## 4. Vollständige Wiederverwendungsprüfung

Der aktuelle Konkurrenzgraph entsteht aus der gemeinsamen P1.4b-Zuordnung,
nicht aus gespeicherten Antworten. Er enthält sämtliche alten Beteiligten,
auch unreferenzierte Rivalen und bislang zugeordnete Eigentümer eines Ziels.
Er wird vor einer Antwort auf Gruppen mit disjunkten Zielmengen geschlossen.
Bereits eindeutig außen belegte Ziele stehen zusätzlich als Reservierung fest.

Eine gespeicherte Gruppe gilt nur, wenn alle folgenden Schritte gelingen:

1. Objekt, vollständige alte Anspruchsmenge und daraus gebildeter Schlüssel
   stimmen. Kein Suchen nach einer passenden Teilmenge älterer Gruppen.
2. Anzahl gespeicherter Kandidaten stimmt mit der aktuellen ganzen Gruppe.
3. Jeden gespeicherten Tabellenfingerabdruck mit dem vorhandenen `resolve`
   gegen **alle** aktuellen Kandidaten dieser Gruppe wiedererkennen.
   Jeder muss eindeutig gewinnen. Die so erhaltenen Ziel-IDs müssen
   paarweise verschieden sein und die ganze aktuelle Kandidatenmenge treffen.
4. Für jede Tabellenzeile stimmt ihre gespeicherte `claims`-Menge mit den
   aktuellen alten Ansprüchen auf das wiedererkannte Ziel überein. Damit
   entwerten zusätzliche/verschwundene Kanten ebenfalls den alten Entscheid.
5. Alle Entscheidungen sind vollständig und zulässig; ihre Ziele sind
   untereinander und gegenüber freigegebenen Außenzuordnungen injektiv.
   Erst danach wird die Gruppe als Ganzes angewandt.

Wenn ein Schritt scheitert, wird die **gesamte** Gruppe erneut gefragt.
Kein Übernehmen einzelner noch passender Altantworten, kein erstes Ergebnis
gewinnt. Alte Einträge dürfen im Dokument erhalten bleiben; nicht exakt
passende Schlüssel und Muster sind inert.

Zwei geometrisch ununterscheidbare neue Kandidaten können trotz vollständig
gespeicherter Antworten nicht dauerhaft wiedererkannt werden. Dann bleibt
`resolve` mehrdeutig und die Gruppe fragt erneut. Eine neue Nummerierung
oder gespeicherte Tabellenreihenfolge ersetzt diesen fehlenden Beleg nicht.
Eine echte Eins-zu-eins-Wiedererkennung ist hier absichtlich strenger als
ein neuer globaler Permutationslöser.

Eine alte Einzelantwort unter `legacy` darf nur den bisherigen gewöhnlichen
Einzelfall lösen: genau ein alter Anspruch, keine konkurrierenden Ansprüche
auf seine Kandidaten und eindeutige Körperzuständigkeit im gesamten
Ausgabesatz dieser Operation. Derselbe alte Name an zwei Ausgabekörpern ist
kein solcher Beleg. Fehlt diese Zuständigkeit, wird gefragt; die Migration
erfindet sie nicht. Neue Antworten werden immer körperqualifiziert gespeichert.

## 5. Fragen und atomare Übernahme

Eine unreferenzierte Gruppe bleibt ohne Dialog offen. Ihre Kandidaten erhalten
keine willkürlich fortgeführten Namen oder Erzeuger. Ist mindestens ein alter
Anspruch referenziert, umfasst die Entscheidung die ganze Gruppe, einschließlich
unreferenzierter Konkurrenten. Ein körperloser Verweis schützt wie bisher alle
tatsächlich betroffenen Körper; er hebt deren Speichertrennung nicht auf.

Ablauf je Gruppe:

1. Alte Ansprüche in stabiler Reihenfolge abarbeiten. Frage beispielsweise:
   „Welches aktuelle Merkmal am Körper {object} soll den bisherigen Bezug
   {name} fortführen? Auch {others} kommen dafür infrage. Jedes aktuelle
   Merkmal kann nur einen bisherigen Bezug fortführen.“
2. Auswahl enthält die für diese alte ID zulässigen **noch freien aktuellen
   neuen Feature-IDs** und „Nicht weiterführen“. Der Text erklärt:
   „Nicht weiterführen lässt bestehende Verweise auf {name} offen.“
   Keine Auswahl einer alten ID als vermeintliche neue Fläche.
3. Auch bei einem einzigen aktuellen Ziel bleibt die Wahl erforderlich,
   wenn mehrere alte Identitäten konkurrieren. Sind nach früheren Antworten
   keine freien Ziele übrig, bleibt die ausdrückliche Nichtfortführung als
   einzige Sachantwort neben Abbruch. Kein automatisch erfundener Verzicht.
4. Entscheidungen nur in einer lokalen Tabelle sammeln. Ein gewähltes Ziel
   wird darin reserviert. Ein unbekannter Antwortstring ist ein Fehler,
   nicht gleichbedeutend mit Nichtfortführung. `None`/Abbruch ist niemals
   eine gespeicherte Nichtfortführung.
5. Nach der letzten Antwort nochmals Abbruch und gesamte Injektivität
   prüfen. Erst dann Mapping und **einen vollständigen Gruppeneintrag**
   erzeugen. Alle nicht fortgeführten alten Namen bleiben über den vorhandenen
   Reservierungsweg gesperrt; zufällig gleichlautende neue Erkennungsnamen
   dürfen alte Verweise nicht wiederbeleben.

Die vorbereitete Ausgabe der Operation bleibt atomar: `prepared_matches`
neben `prepared_objects` führen und erst nach erfolgreicher Vorbereitung
sämtlicher Ausgabekörper in `EvaluationResult.matches[operation.id]`
übernehmen. Ein Abbruch nach der ersten Frage oder im zweiten Ausgabekörper
veröffentlicht weder eine Teilgruppe noch Antworten des ersten Körpers
dieser Operation. Antworten früher bereits abgeschlossener Operationen in
einem zurückgegebenen Teilresultat folgen ihrem bisherigen Vertrag.

`OperationCancelled` ist eine eigene Exception, kein `AppError`; sie läuft
weiter bis zum vorhandenen Arbeiterabbruch. Das normale Anhalten ohne Frager
bleibt `AmbiguityError` und gibt den letzten vollständigen Szenenzustand
zurück. `History.record_matches` erhält nur veröffentlichte vollständige
Einträge, ersetzt pro Schlüssel atomar und kopiert verschachtelte Werte,
damit spätere Änderungen am Ergebnis keine History nachträglich verändern.
Kein neuer Undo-Schritt, kein neuer Auswertungslauf und kein Antwortcache.

## 6. Enger Anschluss der echten Fragevorschau

Ein optionaler Callback an `evaluate` genügt, ohne `AskFn` oder sämtliche
Operationen zu erweitern:

```python
question_context: Callable[
    [EvaluationResult | None, tuple[tuple[ObjectId, FeatureId], ...]], None
] | None = None
```

Die Ausgabeschleife stellt `_with_features` dafür einen gebundenen Helfer
bereit. Unmittelbar vor jeder Gruppenfrage baut er eine reine Vorschau aus
dem vollständigen Zustand vor der Operation, den tatsächlichen aktuellen
Operationsausgaben und den **soeben erkannten** Kandidatenmerkmalen des
gefragten Körpers. Verbrauchte Eingänge werden darin nur für die Anzeige
ersetzt. Ungeprüfte weitere Ausgaben zeigen ihre tatsächliche Geometrie,
keine erfundene Zuordnung. Die Vorschau erhält `stopped_at=operation.id`,
keine erfolgreiche Abschlussbehauptung und keine zu speichernden Antworten.
Sie verändert weder die eigentliche Szene noch Cache oder Dokument.

`question_context(preview, qualified_candidates)` setzt in der Session die
vorhandenen fadenlokalen Vorschau-/Kandidatenwerte; `ask_from_worker` reicht
sie im bestehenden `AskRequest` weiter. `finally` ruft
`question_context(None, ())` und räumt sämtliche temporären Werte ab. Kein
Vorschauzustand darf in eine nachfolgende Einheitenfrage gelangen.

Für diese **temporäre** Vorschau braucht `AskRequest` eine entsprechende
Markierung mit Vorgabe `False`; bestehende Waisenfragen behalten ihren
bisherigen Ergebnisweg. MainWindow zeigt temporäre Matchingvorschauen nur
im Viewport, nicht über den vollständigen `_on_scene`-Abschlussweg. Körper
und alter Bezug stehen im Fragetext; Bericht, Verlauf, gespeicherte Szene,
Dirty-Zustand und `Session.last_result` werden nicht zur halben Ausgabe.

Die Auswahl wird erst freigegeben, wenn
`viewport.is_scene_applied(request.preview)` gilt; ansonsten über das
vorhandene `sceneApplied` warten. Abbrechen bleibt bedienbar. Ein kleiner
Bereitschaftsanschluss am bestehenden `AskDialog` muss auch Doppelklick und
Tastatur vor zu früher Übernahme schützen. Kein blockierendes Polling im
Hauptthread. Danach `show_candidates` mit den körperqualifizierten aktuellen
IDs; die vorhandene Hervorhebung anhand des Rohwerts der Auswahl passt dazu.

Nach Ende der Frage Markierungen entfernen und die letzte tatsächlich gültige
Ansicht wiederherstellen, **bevor** `request.reply` den Arbeiter freigibt.
So kann das abschließende `finally` kein gerade eingetroffenes neues Ergebnis
überschreiben. Auch ein Aufbaufehler muss `reply(None)` erreichen und den
Arbeiter freigeben. Die bestehende Projektgeneration und Arbeiteridentität
bei Auftragserzeugung mitführen: Überholte Fragen weder anzeigen noch
anwenden; bei zwischenzeitlichem Projektwechsel keine alte Szene zurücklegen.
Viewport-Generationen verwerfen verspätete Mesh-Vorbereitungen bereits.

## 7. Migration, History und Funktionsgrenzen

Format 26 → 27: In jeder gespeicherten Operation einen vorhandenen nichtleeren
alten `matches`-Block unverändert als `{"legacy": old_matches}` einbetten.
Fehlende/leere Antworten bleiben fehlend/leer. Keine Gruppe, kein Körperbezug
und keine Nichtfortführung werden aus alten Daten erfunden.

Erfasst werden `ops` sowie jede nichtleere Operation in
`transactions[].changes.before/after.edited_ops`; `None` als gelöschte
Operation bleibt erhalten. Das vorhandene Muster von
`_keep_raw_import_coordinates` zeigt diese Traversierung. Vor-Migrations-
Validierung lässt das alte äußere Schema zu; erst nach der Migration gilt
die neue Gruppenprüfung, auch in Undo-Fassungen. `project.load` besitzt beide
Prüfstellen bereits. Ältere Migrationsstufen bleiben erhalten.

Wichtig: Die Migration 19 → 20 benutzt heutige `document_from_data`-/History-
Funktionen. Deshalb darf `operation_from_data` nicht heimlich schon dort
Altantworten umhüllen. Die Umformung gehört genau in 26 → 27; der Serializer
transportiert die jeweilige Wörterbuchgestalt, ohne eine zweite Migration.

### Die nachträgliche Antwort muss ihre History-Fassung wiederfinden

Konkreter bisheriger Gegenablauf aus dem Code: `change_params` erzeugt
`before=A` und `after=B`; die Auswertung beantwortet eine Frage und
`record_matches` ersetzt nur die aktuelle Operation durch `B+Antwort`.
Undo legt `A` zurück, Redo anschließend das gespeicherte `B` ohne Antwort.
Beim Undo einer neu angelegten Operation besteht diese Lücke nicht:
`_undone_ops` übernimmt dort bereits die aktuelle Operation samt Antwort.

Kleinster vollständiger Anschluss: Beim Verlassen einer bearbeiteten
Operationsfassung ihre aktuellen vollständigen `matches` in die betroffene
bestehende Änderungsseite übernehmen. Vor `undo` ist das die `after`-Seite
der zurückzunehmenden Transaktion; vor `redo` die `before`-Seite der erneut
anzuwendenden Transaktion. Ein gemeinsamer kleiner History-Helfer kopiert
ausschließlich das Antwortfeld der dort tatsächlich enthaltenen, aktuell
lebenden Operationsfassung und ersetzt die entsprechende Änderungsseite.
Kein eigener Speicher, keine zusätzlichen History-Einträge. Die vorhandene
`record_matches`-Meldung bleibt der Abschlussweg während der Auswertung.

Dabei Fassung und nicht nur Op-ID prüfen: Operationsname, Eingänge,
Ausgänge, Parameter, Startwert und übersetzbare Parameterkennzeichnung
müssen zur aktuellen Fassung gehören; die Antwort und die nachträglich
protokollierte Solverauskunft sind keine neue Operationsfassung. `None`
für gelöschte Operationen bleibt unverändert. Eine andere alte Fassung
darf nicht mit der jüngsten Antwort überschrieben werden. Bei mehreren
Undo-/Redo-Schritten wird jeweils nur die gerade verlassene Grenze ergänzt.
Auch nach Speichern/Wiederöffnen trägt der Hauptstapel die aktuelle Antwort,
die vor dem ersten Undo wieder an diese Grenze übernommen wird.

Dieser Anschluss verspricht die Erhaltung des vollständigen Entscheids,
nicht seine bedingungslose Gültigkeit in jeder früheren Geometrie: Nach dem
Zustandswechsel läuft immer die ganze Gruppenprüfung. Ein inzwischen anderes
Kandidatenmuster fragt weiterhin neu. Antworten werden insbesondere nicht
pauschal in alle früheren Fassungen derselben Op-ID verteilt.

Konkrete schmale Zuständigkeiten, keine neue Bibliothek:

| Ort | Funktion/Vertrag |
|---|---|
| `perceive/matching.py` | Gemeinsame Konkurrenzgruppen aus dem aktuellen `MatchResult`; keine zweite Kostenrechnung in der Antwortschicht. `group_key(object_id, old_ids)` für das kanonische Schlüsselformat. |
| `perceive/matching.py` | `group_fingerprint(object_id, claims, decisions, detected, centre, diagonal, *, check_cancelled=None)` schreibt das vollständige obige Schema; `decisions` ist intern alte ID → neue ID oder `None`. |
| `perceive/matching.py` | `resolve_group(saved, object_id, claims, detected, centre, diagonal, reserved_targets, *, check_cancelled=None)` gibt die **vollständige** alte-ID → neue-ID/`None`-Entscheidung oder `None` für „erneut fragen“ zurück. Ein Dict ausschließlich aus Nichtfortführungen ist eine gültige Entscheidung und unterscheidet sich von Rückgabewert `None`. |
| `perceive/matching.py` | `apply_mapping` und `inherit_originators` prüfen denselben injektiven Übernahmevertrag. Sie dürfen niemals per Dict-Reihenfolge den letzten Namen und den ersten Erzeuger verschiedener Vorfahren verbinden. |
| `scene/evaluate.py` | Gruppen fragen/anwenden, Referenzrelevanz, qualifizierter Ausgabezustand, Vorschaukontext, lokale Antwortstufung und ursprünglichen Abbruch zusammenhalten. |
| `scene/project.py` | Eine strukturelle Gruppenprüfung am vorhandenen Operationsschema; keine geometrische Wiedererkennung beim Laden. |
| `scene/history.py` | Ganze Einträge ohne neue Transaktion übernehmen; keine Entscheidungsteile mischen oder nachträglich durch fremde Dict-Mutation verändern. Ein gemeinsamer Helfer sichert vor `undo`/`redo` die Antworten der gerade verlassenen bearbeiteten Fassung in deren bestehender Änderungsseite. |
| `scene/serialise.py` | Verschachtelte JSON-Daten ohne Namen-/Einheitenumdeutung übertragen; keine eigenen Entscheidungsregeln. |
| `ui/session.py`, `ui/main_window.py`, `ui/dialogs.py` | Vorhandenen Ask-/Vorschaukanal und Bereitschaft/Abbruch anschließen; keine neue Auswahloberfläche. |

`check_cancelled` gilt auch während vollständiger Gruppenvalidierung und
unmittelbar vor Veröffentlichung. Alle Wiedererkennungen verwenden das
bestehende `resolve`, alle neuen Fingerabdrücke `fingerprint`. Neue
Toleranzkonstanten oder ein zweiter globaler Zuordnungslöser sind unnötig.

Die Cache-Kompatibilitätsversion ist bei der P1.4b-Umstellung anzuheben:
Vorbereitungs-Ops können bereits innerhalb ihres gecachten Ergebnisses
Merkmalsnamen übernommen haben. Antworten selbst bleiben außerhalb des
Operationshashs; der Antwortvertrag muss auch nach einem Cachetreffer laufen.

## 8. Native Grenze

Der native allgemeine Matchweg übernimmt nur Erzeuger. Echte bestehende
Topologiehistorie aus `ModifiedShape`/Flächenabbildung bleibt ein stärkerer
Beleg und wird nicht durch Mesh-Umbenennung ersetzt.

Bei geometrisch konkurrierenden nativen alten Ansprüchen werden keine
Erzeuger übernommen. Ist einer davon referenziert und fehlt eine echte native
Historienbestätigung, hält die Operation vor Veröffentlichung mit einer
offenen Referenz an. Gleichlautende aktuelle Topologiekennungen dürfen diesen
Halt nicht umgehen. Es gibt hier noch keine scheinbar wirksame Gruppenfrage:
Ein Mesh-Gruppeneintrag ist keine Erlaubnis, native Referenzen oder IDs
umzuschreiben. Native ausdrückliche Referenzneuwahl ist ein gesonderter
Anschluss; bis dahin bleibt dieser Fall ehrlich offen. Unreferenzierte native
Gruppen können mit aktuellen nativen Kennungen und ohne erfundene Herkunft
weiterlaufen. Native und gemischte Ausgaben teilen die atomare Operationsgrenze.

## 9. Minimale Dateiliste und unabhängige Abnahmefälle

Produkt: `app/core/perceive/matching.py`, `app/core/types.py`,
`app/core/scene/evaluate.py`, `history.py`, `migrations.py`, `project.py`,
`serialise.py` nur soweit für Kopie/Vertrag nötig, `cache.py` für die
Kompatibilitätsgrenze; `app/ui/session.py`, `main_window.py`, `dialogs.py`;
alle fünf Sprachkataloge. Die vorhandenen `perceive/`, `scene/`, `ui/`-Karten
und der Dateiformatvertrag ziehen auf ihrer zuständigen Ebene nach.
`Viewport` benötigt nach dem gelesenen Vertrag keine neue Szene-API.

Tests: bestehende `tests/test_spatial_matching.py` bzw. `test_matching.py`
für den Konkurrenzvertrag, `tests/test_evaluation.py` und
`test_matching_cancellation.py` für Gruppenantworten und Abbruch,
`test_project.py`/`test_history.py` für Migration und History.
Eine echte v26-Antwortdatei mit gespeicherten Undo-Fassungen als neue
Korpusdatei ergänzen; bestehende historische Dateien nicht überschreiben.
`example_v27.p3d` ist wegen des vorhandenen Beispieldateivertrags erforderlich.
`tests/test_ui.py` erhält die echten Frage-/Vorschauanschlüsse, bleibt aber
als gesamte Fensterdatei bis zum Release zurückgestellt.

Unabhängig zu belegen:

1. Drei alte gleichwertige Ansprüche auf einen neuen Kandidaten bleiben
   offen. Eine vollständige Antwort führt genau einen alten Namen und dessen
   Erzeuger fort; die anderen Namen sind dauerhaft reserviert.
2. Zwei Ausgabekörper mit demselben alten Namen und gleichen geometrischen
   Fingerabdrücken erhalten verschiedene Gruppenschlüssel und Antworten.
   Eine alte unqualifizierte Einzelantwort darf sie nicht beide freigeben.
3. Neue Kandidatennummerierung ohne geometrische Änderung verwendet die
   Gruppe wieder. Neue/verschwundene alte Beteiligte, Kandidaten oder
   Anspruchskanten fragen erneut; zwei ununterscheidbare aktuelle Zwillinge
   bleiben erneut offen, auch wenn die Anzahl gleich ist.
4. Ein echtes neues Hindernis im Außenmapping und zwei gespeicherte Ziele
   auf denselben aktuellen Kandidaten werden vor jeder Übernahme abgewiesen.
5. Nichtfortführung bleibt nach Speichern/Wiederöffnen ausdrücklicher
   Entscheid. Ein dadurch offener Verweis meldet weiterhin sein echtes
   Problem und wird nicht auf einen gleichlautenden frischen Namen gebogen.
6. Abbruch nach erster Gruppenantwort, Abbruch nach erstem Ausgabekörper,
   fehlender Frager und ungültiger Antwortwert hinterlassen keinen Teilstand
   dieser Operation in Szene, `matches`, History oder Cache.
7. Migration erfasst Hauptstapel sowie beide Undo-Seiten einschließlich
   gelöschter Operationen; ein alter Feature-Name `legacy` wird korrekt
   geschachtelt. Undo/Redo und die gesamte bisherige Migrationskette bleiben
   funktionsfähig. Besonders: Parameter ändern, erst danach antworten,
   speichern/öffnen, Undo/Redo; sowie im zurückgenommenen Zustand antworten,
   Redo/Undo. Jeweils kehrt der richtige Antwortsatz dieser Fassung zurück,
   ohne einen anderen alten Antwortsatz zu überschreiben. Wiederholtes
   `record_matches` ändert das Dokument nicht.
8. Die Vorschau zeigt tatsächliche neue Geometrie/Featureflächen, während
   der vorherige Körper an anderer Stelle liegt und dieselben Erkennungsnamen
   für andere Flächen benutzt. Vor `sceneApplied` ist keine Antwort möglich;
   nach Abbruch bleibt keine Vorschau, nach Projektwechsel keine alte Szene.
   Eine folgende Einheitenfrage besitzt weder Kandidaten noch Vorschau.
9. Native bestätigte Historie bleibt wirksam. Referenzierte Konkurrenz ohne
   diesen Beleg hält trotz gleicher aktueller Namen an; ein gespeicherter
   Mesh-Gruppenentscheid schaltet diesen Halt nicht aus.

Diese Notiz legt den Anschluss fest; sie ist kein Umsetzungs-, Fenster- oder
Leistungsnachweis. Während ihrer Erstellung liefen keine Tests und wurden
keine Produktdateien verändert.
