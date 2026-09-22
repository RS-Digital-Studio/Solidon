# P1.4c – Gegenprüfung des Speichervertrags

Lesestand: eingefrorener P1.4b-Arbeitsbaum auf `ee16040e7`, Projektformat 27,
Cacheformat 20 einschließlich des neuen vollständigen Merkmals-Objekthashes.
Nur Code und Plan gelesen; keine Tests, Sonden oder Produktänderungen.

## Empfehlung

`native-group` mit einem eng definierten `scope` in `Operation.matches` ist
für den geplanten ersten nativen Aliasweg angemessen. Bestehende Referenzen
tragen den Bezug, aber keinen Nachweis seiner bestätigten aktuellen Auswahl.
Ein eigener Antwortspeicher ist nicht nötig. Die Gruppendaten und Validatoren
aus P1.4b wiederverwenden; eine Domänenkennung genügt, nicht zusätzlich noch
ein zweites vollständiges Gruppenschema.

`edge-answer` in demselben Speicher ist für den **vollständigen** geplanten
Kantenweg einschließlich kollidierender Schlüssel die kleinere Erweiterung
des vorhandenen Speicher-/History-Vertrags. Es ist aber eine anders wirkende
Antwort: Sie bestimmt die Geometrie der konsumierenden Operation bereits vor
deren Ausführung. Der Plan muss deshalb einen vor dem Cachezugriff aufgelösten
Selektor und dessen abgeleiteten Verbraucherschlüssel festlegen. Der in P1.4b
reparierte Merkmals-Objekthash allein reicht dafür nicht.

Für die bloße Wahl eines anderen **eindeutigen** vorhandenen `edge_key` wäre
ein neuer `edge-answer` nicht erforderlich: Das ist bereits als Änderung von
`edge_keys` darstellbar. Dieser kleinere Fall darf nicht mit der verlangten
Auflösung zweier verschiedener Kanten mit gleichem Schlüssel verwechselt werden.

## Was bereits vorhanden ist

| Stelle | Tatsächlicher Vertrag und Folgerung |
|---|---|
| `types.py:1613`, `Operation` | Kein Feld `answers`. Vorhanden sind `params` und `matches`. Der Plan sollte nicht auf einen vermeintlichen dritten Speicher verweisen. |
| `types.py:1562`, `OpResult.answered`; `evaluate.py:574`; `history.py:878`, `record_answers` | Der Antwortenweg übernimmt Werte in **Operationsparameter**. Er eignet sich für eine wirklich neue eindeutige `edge_keys`-Angabe; nicht ohne Schema-/Editoränderung für zusätzliche versteckte Scope-/Kandidatenstrukturen. |
| `geom/edge_ops.py:68`, `_chosen_edges`; `FilletParams.edge_keys`; `registry/params.py` | `kind="edges"` ist eine Zeichenkette mit leerzeichengetrennten vorhandenen Schlüsseln. Zwei Kanten mit demselben Schlüssel sind darin weiterhin dieselbe Antwort. Eine neue strukturierte Syntax wäre selbst ein neuer Vertrag, kein kostenlos vorhandener Alternativweg. |
| `types.py:598`, `FeatureRef`; `scene/orphans.py:93`, `references` | Körper und logischer Merkmalsname sowie die Verwendungsstelle werden bereits geführt. Keine geometrischen Wiedererkennungsdaten, keine Kantenwahl und kein bestätigter Scope. `Reference.where/index` kann die Verwendung lokalisieren, sollte aber keine Kante als `FeatureId` tarnen. |
| `sketch/planes.py:96/106/120`; `sketch/ops.py:256`, `_height_of` | Neue Ebenen können `feature:object_id:feature_id` tragen. Die alte unqualifizierte Form und `up_to` lösen noch über die Szene auf. Diese Referenzqualifikation ist wiederverwendbar; sie ersetzt keinen nativen Auswahlbeleg. |
| `history.py:914`, `record_matches`; `:1422`, `_remember_version_matches` | Ganze Antwortdatensätze werden bereits tief kopiert und an die passende Vorher-/Nachher-Fassung gebunden. Eine zweite Answer-History ist für zusätzliche `matches`-Domänen unnötig. |
| `serialise.py:523/547`, `operation_to_data/from_data` | Verschachtelte `matches` werden bereits vollständig tief kopiert. Nur neue Schlüssel und primitive Scope-/Fingerprintdaten verlangen hier keinen neuen Codec. |
| `ui/session.py:3241`, `_on_finished` | Der aktuelle Fertigweg schreibt `result.answers` und `result.matches` über die History und setzt Dirty. Diesen Abschluss benutzen; keine zusätzliche direkte Umschreibung aus dem Fragedialog. |

Der Parameterweg wäre für die vollständige Kantenwahl möglich, aber nicht
automatisch kleiner: Er verlangte eine neue kollisionsfreie `edge_keys`-Syntax,
Anpassungen sämtlicher Leser/Editoren und einen ausdrücklichen Abschluss der
nachträglich beantworteten Parameter an gespeicherten History-Fassungen.
`record_answers` vereinigt derzeit nur `params`; `_remember_version_matches`
übernimmt dagegen ausdrücklich nur `matches` und verlangt gleiche Parameter.
Die schon vorhandene Tiefen-/Fassungsbindung der Zuordnungsantworten ginge bei
einem Wechsel zum Parameterweg nicht automatisch mit.

## Unverzichtbare Präzisierungen gegenüber dem Plan

### 1. Die Kantenentscheidung muss vor dem Verbrauchercache wirken

Beweis im Kontrollfluss: `evaluate.py:460` berechnet den Operationsschlüssel,
`:481` liest `cache.get(key)`, erst im Miss-Zweig läuft `spec.fn(context)`.
`hashing.operation_hash` liest Parameter und Eingangs-Hashes, keine `matches`.
`edge_ops._on_a_solid` und `brep.edit.fillet/chamfer` führen danach die konkrete
Kantenbearbeitung aus. Bei unverändertem Eingang und unveränderten `edge_keys`
könnte eine geänderte `edge-answer` andernfalls das vorige Ergebnis aus dem
Verbrauchercache erhalten.

Minimaler Ablauf: alle aktiven ausdrücklichen Kantenreferenzen am aktuellen
Eingang auflösen → vollständige Wahl bestätigen → daraus einen stabilen
Selektor-Digest bilden → diesen als zusätzlichen **fachlichen Eingang dieses
Verbrauchers** in dessen vorhandene Schlüsselaufbereitung geben → Cache lesen
oder exakt dieselbe Auswahl an den Builder übergeben. Der Digest stammt aus
der tatsächlich aufgelösten Auswahl; weder Fragetoken noch bloß der gespeicherte
Antwortdatensatz genügen. Kein persistierter zweiter Antwortcache und kein
pauschales Einbeziehen aller `Operation.matches` in den Operationshash.

Native Merkmalsgruppen bleiben hingegen im bisherigen Ablauf nach dem
Erzeugercache: Alias auf aktuelle vollständige Merkmalsdaten, danach der schon
vorhandene `object_hash(features=...)`. Dessen Beleg ist bereits implementiert;
hier keine zweite Hash- oder Feature-Serialisierung hinzufügen.

### 2. Ausgabe- und Eingangsbesitz nicht vermischen

`match_records.validate_group/validate_matches` prüfen derzeit alle neuen
Gruppen gegen `operation.outputs`. `project._validate_operation_schema:873`
übergibt nur diese Ausgaben. Native Aliasgruppen gehören weiterhin genau dort
hin; eine Kantenantwort gehört zur **konsumierenden** Operation und ihrem
konkreten **Eingang**, zusätzlich zum registrierten Feld und vollständigen
ursprünglichen Auswahlbündel.

Der gemeinsame Validator braucht daher eine enge Domänenunterscheidung und
die passenden Ein-/Ausgangskennungen. Die Registry prüft zur Laufzeit, ob das
benannte Feld tatsächlich ein aktives `edges`-Feld ist; der Projektleser
rechnet weder Geometrie noch Kandidaten. Eine ganze Mehrfachwahl ist ein
Datensatz. Einzelne Entscheidungen dürfen nicht unabhängig nachgetragen werden.

`History._copy_operation_matches:151` filtert bei Ausgabewechsel derzeit
ausschließlich nach `object_id in outputs`. Diese Stelle ist die nötige
History-Anpassung für eingangsgebundene Kantenantworten: Ein-/Ausgangswechsel
domänengerecht behandeln, alte Antworten nur in der alten Fassung bewahren.
Kein Umbenennen auf neue Körper. Die schon bestehende allgemeine Tiefenkopie
und `_remember_version_matches` können für beide Antwortdomänen bestehen bleiben.

### 3. Scope eng und ohne Selbstbezug festlegen

Für native Aliasgruppen reicht der rohe Erzeugerschlüssel plus Ausgabeindex
als konservative Fassungsgrenze, zusammen mit bereits gespeichertem Körper und
Anspruchssatz. Nicht den **nach Aliaswahl** gebildeten Objekthash verwenden:
Er enthält die Entscheidung selbst und würde den Wiedererkennungsbezug zirkulär
machen. Qualität, Profil, Quellen- und Implementierungsstand gehen heute in den
Erzeugerschlüssel ein; zusätzliche Rückfragen bei deren Änderung sind die
bewusst enge Grenze dieses Ansatzes.

Die Kantenwahl bindet dagegen an den bereits veröffentlichten Eingangsstand.
Sie muss außerdem zum Feld, Auswahlmodus und ursprünglichen vollständigen
Schlüsselbündel passen. Eine spätere andere Einzelwahl oder der Wechsel zu
einer Richtungsgruppe darf nicht von einem alten Antwortdatensatz überschrieben
werden. Die konkrete Digest-Zusammensetzung und das Feldschema fehlen im Plan
noch; vor der Implementierung genau einmal festlegen.

Scope ist eine Sperre gegen Wiederverwendung auf einer anderen Fassung,
kein Topologiebeweis. Vollständige eindeutige Wiedererkennung und aktuelle
Auswahlfähigkeit bleiben zusätzlich Pflicht. Die vorhandenen knappen
Fingerabdrücke beweisen für sich keine gleiche Trimmung oder Kurvenidentität.
Ein stärkerer vollständiger Geometrienachweis könnte die Scope-Grenze später
ersetzen; ihn jetzt nur wegen eines eingesparten Feldes neu zu bauen wäre größer.

## Welche Format- und Cachearbeit wirklich nötig ist

| Änderung | Notwendiger Umfang |
|---|---|
| Projektformat 28 | **Ja**, sobald native Domäne/Scope oder Kantenantworten gespeichert werden. Der aktuelle v27-Validator akzeptiert genau vier Gruppenfelder und den `group:`-Schlüssel. Ein v27-Leser darf die neue Antwort nicht als v27-Daten interpretieren. Die vorhandene Too-new-Grenze in `project._validate_project_schema`/`migrate` soll greifen. |
| Migration 27→28 | **Ja als eigener Formatschritt, keine erfundene Datenumschreibung.** Wenn alte Gruppen gültig bleiben, kann die Migration sie inhaltlich unverändert lassen. `group:` und `legacy` weder erneut umhüllen noch als nativ markieren; insbesondere keine Scope-Werte aus ungeprüfter Dateigeometrie erzeugen. Alte Haupt- und Undo-Seiten bleiben vollständig erhalten. Eine v27-Beispieldatei existiert bereits; ihre Öffnung und unveränderten Antworten durch alle Fassungen prüfen. |
| Serializer | **Keine Änderung allein für die vorgeschlagenen primitiven Datensätze.** Der vollständige tiefe `matches`-Codec besteht. Native Handles, Topologieindizes oder vollständige Körper-/Merkmalsresultate dürfen dort nicht entstehen. |
| History | **Enger Besitzfilter für Eingangsantworten**, keine neue Verlaufsebene. Einfache Scope-/Native-Gruppenergänzung allein erfordert keine neue Kopierlogik. Parameterantworten wären separat auf tatsächliche Undo-Fassungen anzuschließen. |
| Feature-/ResultCache-Codec | **Keine weitere Erweiterung allein wegen neuer Antworten.** `cache.feature_to_data` und `object_hash(features=...)` tragen bereits aktuelle Parameter, Dreiecke, Teilträger, Quellen und Erzeuger. |
| Cacheentwertung | Der Kanten-Verbraucherschlüssel muss den aktuellen aufgelösten Selektor berücksichtigen. Geändertes natives Verbraucher-Verhalten muss den vorhandenen Implementierungsstand (`OperationSpec.cache_version`) bzw. bei allgemeiner neuer Merkmalsauskunft die zentrale Cacheversion entwerten. Projektformat 28 erzwingt für sich keinen weiteren globalen Cacheformatsprung. |

## Mindestinvarianten für die Umsetzung

1. Genau eine Antwortdomäne und der richtige Operations-/Körper-/Feldbesitz;
   native Zustimmung wird nie aus einer Netzgruppe oder Namensgleichheit erzeugt.
2. Ganze Anspruchskomponente bzw. ganze Kantenauswahl, injektiv und ohne
   Doppelbesitz. Nichtfortführung ist ausdrücklich; Abbruch ist keine leere
   Auswahl und niemals der Rückfall auf „alle“.
3. Vor jedem Wiederverwenden aktueller Scope, vollständig erneut erkannte
   Kandidaten und der vom Verbraucher verlangte Vollflächen-/Kantennachweis.
4. Die bestätigte aktuelle Auswahl erreicht über die echte private Kopierabbildung
   den Builder. Keine zweite Nächstensuche und keine erneute Auflösung über einen
   kollidierenden gerundeten Schlüssel.
5. Der Cache unterscheidet tatsächlich verschiedene Bindungen an der richtigen
   Grenze: Flächenalias beim Ausgabehash, Kantenselektor vor dem Verbrauchercache.
6. Antwortveröffentlichung erst nach vollständig erfolgreicher Operation, mit
   demselben Abbruchtoken; keine erste Teilantwort bei Fehler an Körper oder
   Auswahlteil zwei. Deepcopy sowie Save/load/Undo/Redo bleiben fassungsgebunden.
7. Vorhandene körperqualifizierte Referenzen weiterverwenden; unqualifizierte
   Ebenen und Zielflächen bei Konkurrenz offenhalten. Keine Migrationsentscheidung
   für den Kunden, keine OCCT-Unterformkennungen als gespeicherter Ersatzbeweis.

Der Plan kann mit diesen engen Präzisierungen weiterverwendet werden. Unverändert
ist insbesondere die Cacheaussage für eine in `matches` liegende Kantenwahl noch
nicht ausreichend; eine breite Serializer-/History-Neuentwicklung ist hingegen
nicht erforderlich. Dies ist eine lesende Vertragsprüfung, keine Produkt- oder
Fensterabnahme.
