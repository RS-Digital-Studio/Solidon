# P1.4c – echte Neuwahl nativer Referenzen

## Ziel und Reichweite

Eine offene native Referenz wird am tatsächlich neu entstandenen Zwischenkörper
gewählt. Die bestätigte Auswahl muss bis zum ausführenden Kernel dieselbe
Fläche oder Kante bezeichnen. Speichern, Cachetreffer und Undo/Redo dürfen keine
andere Auswahl unterschieben. Die Neuwahl ist eine ausdrückliche Nutzerbindung,
kein nachträglicher Beweis einer OCCT-Vorgängeridentität.

Die kleinste vollständige Lösung braucht zwei zusammengehörige Anschlüsse:
Flächen-/Merkmalsbezüge und ausdrücklich gewählte Kanten. Flächenfragen allein
lösen die Kantenreferenzen nicht. Eine allgemeine langlebige OCCT-Namenshistorie
für sämtliche Booleschen Operationen ist dafür nicht Voraussetzung; ohne solchen
Nachweis darf der erste Anschluss konservativ erneut fragen.

Lesestand: P1.4b-Arbeitsbaum nach dem Matcher-Freeze D76E399D…; die Root-Integration
lief parallel. Dieser Plan enthält keine Produkt-/Test-/ROADMAP-Änderung. Es wurde
für diesen Plan kein Test gestartet. Die später ausdrücklich beauftragte enge
Folgecache-Sonde ist unten als eigener Nachweis abgegrenzt.

## 1. Tatsächliche Datenwege

| Bereich | Aktueller Vertrag und konkrete Stelle |
|---|---|
| Native Erkennung | `brep/features.py:features_of` nummeriert `face_1`, `hole_1` usw. je Art neu. Die Nummer ist **kein** Index in `Solid.faces()`. Zusammengefasste Langlöcher, Ringe und Innenräume können mehrere native Flächen umfassen. |
| Auswahl | `Feature.face_indices` sind aktuelle Tessellierungsdreiecke. `kernel.Solid.faces_of_triangles` führt zur aktuellen nativen Fläche; `complete_faces_of_triangles` beweist die vollständige Flächenauswahl. Gleiche oder gültig aussehende Zahlenräume sind kein Herkunftsbeleg. |
| Kopie | `Solid._copied_faces`, `copy_shape` und `edit.transformed_with_faces` führen die tatsächlichen nativen Kopien nach. `geom/transform.py:apply` nimmt darüber vollständige Merkmalsflächen samt Teilträgern mit. |
| Attribute | `carried_face_slots` arbeitet nur bei vorhandenen Filamentwerten, nimmt je Ergebnisfläche gegebenenfalls die erste attributierte Quelle und vereinigt gleiche Slotwerte. Das ist weder vollständige Herkunft noch Injektivität alter Merkmalsidentitäten; Kanten fehlen ganz. |
| Aktuelle native Sperre | `scene/evaluate.py:_with_features` ruft bei nativer Neuerkennung `match` für Erzeugerübernahme auf und hält bei referenzierter Konkurrenz an. Die allgemeine Namenübernahme des Netzes findet dort nicht statt. Gleiche neue Namen sind kein Fortführungsbeleg. |
| Vorhandene gezielte Aliasnamen | `geom/prepare_ops.py:_preserved_exact_features` nach `resize_hole` verwendet bereits `match/apply_mapping` auf neu erkannten **Merkmalen**. Die aktuelle Bohrung und ihr belegter Boden werden mit der Änderungsabsicht nachgeführt. Es werden keine OCCT-Unterformen umbenannt. Diese gemeinsame Aliasmechanik ist nutzbar, ihr spezieller Absichtsbeleg darf aber nicht auf beliebige Operationen ausgedehnt werden. |
| Flächenoperation | `geom/face_ops.py:_on_a_solid` liest das gewählte Merkmal, übergibt aber nur Normale/Mitte an `brep/profiles.py:push_faces`. `_nearest_face` sucht danach erneut die nächste Fläche. Ein bestätigter Merkmalsname erreicht den Kernel bisher nicht als ausdrückliche native Auswahl. |
| Verrundungsmerkmal | `geom/prepare_ops.py:_exact_fillet` reicht Mitte/Radius an `brep/edit.py:unround/reround`; `_cylinder_at` sucht die Rundungsfläche erneut geometrisch. Auch dieser Pfad muss eine ausdrücklich gewählte native Auswahl direkt annehmen. |
| Skizze/Zielfläche | `sketch/planes.py:frame_for` liest Körper-/Merkmalsnamen, Normale und Mitte. `sketch/ops.py:_height_of` benutzt denselben Weg für `up_to`. Die Zeichenebene ist eine logische Flächenreferenz, kein OCCT-Handle. Alte unqualifizierte Ebenen und das heutige `up_to` benötigen gesonderte Körperprüfung. |
| Weitere Merkmalsverbraucher | `scene/placement.py`, `scene/fits.py`, Bausteinplatzierung, `geom/attributes.py`, `geom/prepare_ops.py`, Textur-/Dichtungswege lesen die aktuellen Merkmalsparameter oder Dreiecke. Native Vollflächenattribute benutzen bereits die Vollständigkeitsprüfung. |
| Kanten | `geom/edge_ops.py` speichert `edge_keys` mit Schemaart `edges`; `brep/edit.py` teilt `geom/edges.py:edge_key/named_edges/wanted`. Schlüssel sind geometrisch und gerundet, keine Feature-IDs. Mehrdeutige Schlüssel stoppen; fehlende Teilmengen werden nicht still bearbeitet. |
| Kantenoberfläche | `main_window.py:_edge_names` bildet ein Wörterbuch Schlüssel→Text; gleiche Schlüssel können deshalb keine zwei unterschiedlichen Antworten tragen. `viewport.py` führt eine eigene tatsächliche Kantenauswahl. Eine Neuwahl darf die alte Schlüsselkollision nicht erneut in dieselbe Zeichenkette schreiben. |
| Verweise | `scene/orphans.py:references` liest Passungsseiten, registrierte `feature`/`features`-Felder und Skizzenebenen. `edges` gehört bisher nicht dazu. `_resolves` prüft nur die Namensexistenz; ein neu belegtes gleichlautendes natives `face_1` wird dadurch nicht als fremd erkannt. |
| Verlauf/Frage | `History.record_matches` schreibt vollständige Gruppenantworten ohne zusätzliche Transaktion und übernimmt sie an Undo-/Redo-Grenzen. `orphans.check` dagegen schreibt einzelne Parameter/Passungen direkt und nacheinander um. Seine Öffnungsschleife ist kein atomarer Ersatz für die neue Bindung. |
| Agent | `agent/checks.py` reicht angehaltene Auswertung und deren konkrete Befunde weiter; `AgentSession` benutzt dieselbe Auswertung. Neue native Fragen gehören weiterhin in den vorhandenen Ask-/Kontextweg, nicht in einen Sonderweg des Agenten. |

## 2. Gewählter kleinster Ansatz: logischer Alias mit geprüfter aktueller Auswahl

`Feature.id` bleibt die logische Referenz. Ein bestätigter Alias darf auf das
aktuelle erkannte Feature gelegt werden, einschließlich **dessen** Parametern,
Maßquellen, Dreiecken und Teilträgern. Die Topologieliste des Solid wird nie
umbenannt oder in die Reihenfolge alter Merkmale gezwungen. Ein zweiter Eintrag
mit dem frischen Namen daneben wäre ein Zwilling und wird durch die vorhandene
eindeutige Namenübernahme vermieden.

Damit kann die gemeinsame `apply_mapping`-Mechanik hinter einer nativen Grenze
weitergenutzt werden. Diese Grenze ist neu und darf nicht lediglich den jetzigen
nativen Fehler durch `_answer_matches` plus `apply_mapping` ersetzen:

1. Der Aufrufer hält den aktuellen Solid und dessen tatsächlich neu erkannte
   Merkmale zusammen. Eine Auswahl aus dem alten Körper wird nicht übernommen.
2. Jeder gewählte Nachfolger muss in dieser aktuellen Merkmalsmenge liegen.
   Seine Dreiecke müssen über die aktuelle native Tessellationskarte auflösbar
   sein. Leere, fremde oder ungeklärte Auswahlen bleiben offen.
3. Vollflächenverbraucher verlangen zusätzlich den bestehenden vollständigen
   Flächennachweis; ein semantisches Teilmerkmal wird nicht auf die ganze
   berührte native Fläche erweitert. Ein Mehrflächenmerkmal bleibt eine Menge,
   kein willkürlich gewähltes erstes Face.
4. Gruppenentscheidungen sind vollständig und gemeinsam injektiv. Die gesamte
   Anspruchskomponente einschließlich nicht weitergeführter Namen bleibt wie
   in P1.4b erhalten. Kein offener Gruppenkandidat gehört gleichzeitig einem
   freigegebenen Außenpartner.
5. Erst danach wird das aktuelle Feature mit seinem bestätigten logischen Namen
   veröffentlicht. Erzeugerübernahme, Reservierung und Quellentransport benutzen
   die vorhandenen gemeinsamen Helfer.

Eine bereits von der erzeugenden Operation ausdrücklich ausgegebene, fachlich
belegte Aliasauskunft wie beim gezielten Bohrungswechsel wird zuerst berücksichtigt.
Sie darf nicht durch einen zweiten, absichtslosen Größenvergleich wieder verloren
gehen. `provenance="generated"` allein ist aber kein solcher geometrischer Beleg.

**Verwaisung gehört dazu:** Nicht nur `ambiguous ∩ referenced`, sondern auch ein
referenzierter verlorener/ungeprüfter Name darf nicht durch zufällige neue
Namensgleichheit wieder gültig werden. Bei unterlassener Erkennung oder einer
Grenzüberschreitung ist der Bezug unbekannt. Ein Name aus `reserved_feature_ids`
beweist seine frühere Vergabe, nicht seine aktuelle Fläche.

## 3. Schmale Laufzeit-API

Vorschlag zur Festlegung vor der Implementierung; keine dieser Signaturen ist
bereits vorhanden:

```python
# app/core/brep/features.py – liest ausschließlich den aktuellen Eigentümer.
def native_feature_faces(
    solid: Solid,
    feature: Feature,
    *,
    whole_faces: bool,
    cancelled: CancelToken | None = None,
) -> tuple[int, ...]: ...

# app/core/brep/kernel.py – keine Suche nach einem ähnlichen Ersatz.
def copy_selected_faces(
    solid: Solid,
    face_indices: Sequence[int],
    *,
    cancelled: CancelToken | None = None,
) -> tuple[Solid, tuple[int, ...]]: ...
```

Die erste API benutzt `faces_of_triangles` bzw. `complete_faces_of_triangles`;
`face_indices` der zweiten API bezeichnet ausdrücklich den **nativen** Indexraum
und wird erst aus der ersten Antwort aufgebaut. Vorher wird das Feature über
seinen Namen am aktuellen `SceneObject` gelesen, nicht von einem fremden Körper
als loses Objekt angenommen. Das Kopierergebnis enthält Indizes seiner eigenen
privaten Shape; die Abbildung kommt aus der tatsächlichen Kopie. Namen, OCCT-
Handles und Indizes werden nicht als dauerhafte Referenz serialisiert.

`profiles.push_faces` bekommt einen optionalen ausdrücklichen Flächenselektor.
Bei einem gewählten Feature führt `face_ops` ihn zu; nur der bestehende ältere
Richtungsmodus ohne gewähltes Feature benutzt weiterhin `_facing/_nearest_face`.
Der ausdrückliche Weg darf niemals darauf zurückfallen. Dasselbe gilt für
`edit.unround/reround` und ihren Verbraucher `_exact_fillet`. Anzahl und zulässige
Trägertypen prüft die jeweilige Operation: verlangt ihr Algorithmus genau eine
Rundungsfläche, wird eine mehrteilige Auswahl nicht auf das erste Element gekürzt.

Der private Kopierweg für Kanten braucht die entsprechende echte Edge-Abbildung
über den Kopierer. `_copied_faces` darf nicht für Kanten zweckentfremdet werden.
Kein neuer universeller Topologienamensdienst: zwei begrenzte Auswahltransporte
für die tatsächlich arbeitenden Kernel-Aufrufe genügen.

## 4. Persistenz und Wiedererkennung

Weiterhin **ein** Antwortspeicher: `Operation.matches`. Native Merkmalsentscheidungen
benutzen den vollständigen P1.4b-Gruppeninhalt, werden aber explizit als native
Auswahl gekennzeichnet. Eine Netzantwort darf beim Kernwechsel nicht automatisch
zur nativen Bestätigung werden. Vorschlag: eigener kanonischer Schlüsselraum
`native-group:[object_id, sorted_old_ids]`, strukturell dieselben Gruppenfelder,
zusätzlich ein `scope` für die Fassung des erzeugenden Ergebnisses.

```json
{
  "native-group:[\"obj_1\",[\"face_1\",\"face_2\"]]": {
    "object_id": "obj_1",
    "old_ids": ["face_1", "face_2"],
    "scope": "digest-of-producer-revision-and-output-index",
    "candidates": [
      {"fingerprint": {"kind":"face","relative":[0,0,0.1],"axis":[0,0,1],"diameter":64,"directional":true}, "claims":["face_1","face_2"]},
      {"fingerprint": {"kind":"face","relative":[0,0,0.2],"axis":[0,0,1],"diameter":64,"directional":true}, "claims":["face_1","face_2"]}
    ],
    "decisions": {"face_1":{"candidate":1}, "face_2":{"not_carried":true}}
  }
}
```

Im Beispiel ist `diameter=64` der unveränderte **Flächeninhalt** 64 mm²; der
historische Feldname wird weder umgedeutet noch normiert. Das Beispiel legt
keine neue Toleranz fest.

Der kleinste sichere Umfang akzeptiert gespeicherte native Entscheidungen nur
bei passender Erzeugerfassung **und** vollständiger eindeutiger geometrischer
Wiedererkennung aller Gruppenkandidaten. Der bestehende Erzeuger-Operationshash
plus Ausgabeindex kann zunächst den Scope liefern. Er umfasst derzeit auch
Qualität und Profil; deren Änderung kann deshalb konservativ erneut fragen.
Das ist eine benannte Grenze dieses ersten Anschlusses, kein fertiger
allgemeiner Topologiehistoriennachweis. Eine später belegte native Historie kann
diesen engen Wiederverwendungsbereich erweitern; sie wird hier nicht vorgetäuscht.

Ein Gruppenkandidat muss bei Wiederherstellung weiterhin dieselbe vom Verbraucher
verlangte Auswahlfähigkeit besitzen. Geteilt, zusammengefasst, teilweise abgedeckt
oder ohne eindeutige aktuelle Flächenabbildung bedeutet erneut wählen. Der rohe
Scope ist niemals Ersatz für diese Prüfung oder für den vollständigen Fingerprint-
Vergleich. Namen, Auswahlreihenfolge und identische Maße allein reichen nicht.

Formatfolge: Bei P1.4b als Version 27 benötigt der neue Schlüssel-/Scopevertrag
**28 mit eigener Migration 27→28**, Strukturvalidierung und alter Beispieldatei.
Die alten Netzgruppen und Legacy-Abdrücke bleiben lesbar; es werden keine nativen
Zustimmungen daraus erzeugt. `match_records` bleibt die eine Strukturquelle;
`match_decisions` teilt Gruppen-/Wahlprüfung, erhält aber eine ausdrückliche
Domäne statt eines zweiten Kopierschemas. Keine Geometrie und keine nativen
Indizes kommen in die Projektdatei.

## 5. Kanten: eigener Selektor, gemeinsame Frage- und Verlaufskette

Kanten sind keine `Feature`-Identitäten. Der minimale vollständige Anschluss:

- Registrierte `kind="edges"`-Felder werden als solche erfasst, samt Op-ID,
  Eingangsobjekt, Feld und Position im ausgewählten Schlüsselbündel. Die bestehende
  Registerauskunft wird erweitert; keine zweite hart codierte Operationsliste.
- Die Operation löst ihr vollständiges Kantenbündel am tatsächlichen Eingang auf.
  Eindeutige vorhandene Schlüssel behalten den bisherigen Weg. Fehlende oder
  kollidierende Schlüssel erzeugen eine Neuwahl, keine Teilbearbeitung.
- Jede angebotene aktuelle Kante bekommt ein nur für diese Frage gültiges Token.
  Der Kernel erhält nach der Wahl das zugehörige echte `EdgeInfo` über seine
  private Kopierabbildung. Er bekommt nicht erneut denselben kollidierenden
  gerundeten Schlüssel zum nochmaligen Nachschlagen.
- Das gespeicherte Ergebnis liegt körper-/operations-/feldqualifiziert ebenfalls
  in `Operation.matches`, getrennt von Merkmalsgruppen. Es hält Eingangsscope,
  vollständiges Kandidatenmuster und die gewählten geometrischen Abdrücke.
  Die geometrischen Zahlen kommen ungerundet aus derselben vorhandenen
  Kantenauskunft (`middle`, `direction`, `length`, `extent`), plus vorhandene
  Schlüssel. Es entsteht keine zweite Kurveneinpassung und keine neue
  Akzeptanztoleranz. Für den engen ersten Umfang dürfen diese Abdrücke bei
  gleichem Scope nur exakt und beidseitig eindeutig wiedergefunden werden.
- Ein Rohdaten-Fingerprint ist kein vollständiger Kurvenidentitätsbeweis über
  geänderte Geometrie hinweg; deshalb ist der Scope hier verpflichtend. Sind
  zwei aktuelle Kanten auch darin identisch, ist eine gespeicherte Wiederwahl
  nicht bewiesen und bleibt offen. Kein alter Index löst die Gleichheit auf.
- Die neue Feldstruktur wird zusammen mit den nativen Merkmalsgruppen in v28
  festgelegt. Explizite Kantenlisten dürfen bei Nichtwahl nicht leer werden und
  dadurch auf eine ganze Richtungsgruppe zurückfallen. Abbrechen bleibt offen;
  bewusstes Ändern des Auswahlmodus ist eine normale Parameteränderung.

UI-Anschluss: `FeatureQuestionContext` kann nur Merkmalsziele tragen. Für Kanten
braucht der vorhandene Fragekontext einen expliziten Zieltyp mit aktuellem Körper,
Fragetoken und darstellbarer Kantenauswahl; keine als `FeatureId` getarnte Kante.
Viewport und Auswahldialog dürfen Kandidaten nicht über ein Wörterbuch mit dem
kollidierenden alten `edge_key` entdoppeln. Gezeichnet wird die tatsächlich
angebotene Kante am Frage-Zwischenkörper. Der Ask-Vertrag bleibt Text plus
Antworttoken; Qt und native Handles wandern nicht in den Antwortdatensatz.

## 6. Auswertung, Cache, Verlauf und Agent

1. Nach dem Rohgeometriecache werden aktuelle native Merkmale und Fragen samt
   tatsächlichem Zwischenkörper vorbereitet. Alle Ausgaben einer Operation
   bleiben bis zum vollständigen Entscheid privat.
2. Vor Geometrieausführung eines Konsumenten werden seine vollständigen
   Merkmals-/Kantenreferenzen im aktuellen Eingang aufgelöst. Gebundene
   Skizzenebenen und Zielflächen müssen denselben körperqualifizierten Weg
   nehmen; eine doppelte unqualifizierte `face_1` wird nicht am ersten Objekt
   gefunden. Alte unqualifizierte Daten bleiben ein ausdrücklicher Klärungsfall.
3. Unterschiedliche bestätigte Bindungen verändern den Eingangs-/Folgehash.
   Der Rohkörpercache der fragenden Erzeugeroperation darf unabhängig bleiben.
   Ein abgeleiteter Bindungsdigest aus tatsächlicher ID→Auswahl-/Merkmalsauskunft
   ergänzt den publizierten Objekthash; kein zweiter persistierter Antwortcache.
   Der gemeinsame Featurecodec ist wiederzuverwenden statt dieselben Parameter
   von Hand ein zweites Mal aufzuzählen.
4. `History.record_matches` erhält erst die vollständig geprüften Entscheidungen.
   Undo/Redo, Editieren und Kernwechsel müssen jeweils die passende Fassung
   wiedergeben; ein abgebrochener zweiter Körper schreibt keine erste Teilwahl.
5. `orphans` wird für native Referenzen nicht allein wegen Namensexistenz
   beruhigt. Die neue Bindungsgrenze hat Vorrang. Seine bisherige sequenzielle
   Dokumentumschreibung darf keine teilweise native Gruppenbestätigung erzeugen.
   Bestätigte Nichtfortführung lässt den konkreten Folgeverweis offen bzw. bietet
   dessen bewusste Bearbeitung an; keine stille Koordinaten- oder Vollkörpervorgabe.
6. UI, Agent, CLI und Vorschau benutzen dieselbe Auswertung. Ohne Ask-Antwort
   entsteht ein konkreter Fehlerbericht mit betroffenen körperqualifizierten
   Verweisen und Rückweg zur Neuwahl. Der Agent bekommt keine stillen IDs und
   darf einen angehaltenen Vorschlag nicht automatisch als vollständig übernehmen.
7. Abbruch wird bei Kandidaten-, Flächen-, Kanten- und Kopierschleifen und vor
   Publikation geprüft. Nach Abbruch keine Antwort, keine teilweise Bindung,
   kein Folgecache und keine hängen gebliebene Auswahlhervorhebung.

### Gesonderter inzwischen belegter Folgecachefehler

Auf ausdrücklichen Zusatzauftrag wurde nur die Sonde
`p14b-follow-cache-probe.py` ausgeführt. Zwei echte alte Bohrungen bei y=±3 werden
zu zwei echten neuen Bohrungen bei x=±3. Zwei vollständige Gruppenwahlen vertauschen
die alten Namen; ein `at_feature`-Verbraucher erzeugt eine Markierung am gewählten
Loch. Warmer Cache: linke erste Wahl x=-3, rechte zweite Wahl **weiter x=-3**;
frischer Cache derselben rechten Wahl x=+3. Der Verbraucher wurde beim warmen
Rechtslauf nicht erneut ausgeführt, alle drei Zugriffe waren echte Cachetreffer,
Ausgabehashes und reservierte Namen waren identisch. Direkter Exit **1** im
unveränderten `p14b-follow-cache-two-claims.txt`.

Der erste Versuch mit nur einem alten Anspruch veränderte den reservierten
Namenssatz und reproduzierte den Produktfehler nicht; sein abschließender
Diagnosezugriff hatte einen Sonden-KeyError. Er steht separat in
`p14b-follow-cache-red.txt` und ist kein Fehlernachweis für das Produkt.
Root hat den belegten Cacheanschluss für P1.4b korrigiert. Die unveränderte
Zwei-Ansprüche-Sonde wurde genau einmal erneut ausgeführt: direkter Exit **0**
in `p14b-follow-cache-two-claims-green.txt`. Linke Wahl x=-3, warme rechte Wahl
x=+3, frische rechte Wahl x=+3. Die beiden Erzeuger bleiben Cachetreffer;
der Verbraucher erhält einen anderen Schlüssel und rechnet erneut. P1.4c muss
diesen korrigierten Vertrag übernehmen, keine zweite Lösung hinzufügen.

## 7. Minimale Dateipakete

- **Gemeinsame Antwort-/Auswertungsgrenze:** `perceive/match_records.py`,
  `match_decisions.py`, `scene/evaluate.py`, `scene/orphans.py`; ergänzter
  Kantenreferenztyp und Fragekontext in `types.py`. Matchingkosten bleiben
  unverändert. Ein nativer Auswahlhelfer gehört zu `brep/features.py`, nicht
  in eine neue zweite Wahrnehmungsschicht.
- **Tatsächlicher nativer Verbraucher:** `brep/kernel.py` für ausgewählte private
  Kopien, `brep/profiles.py`, `brep/edit.py`; Anschluss in `geom/face_ops.py`,
  `geom/edge_ops.py` und dem begrenzten `_exact_fillet`-Pfad von
  `geom/prepare_ops.py`. Bestehende deklarierte native Aliasnamen mitprüfen.
- **Projekt und Verlauf:** `scene/migrations.py`, `serialise.py`, `project.py`,
  `history.py` und alte Beispieldatei. Hash-/Cacheanschluss gemäß P1.4b-Korrektur;
  nur bei tatsächlichen neuen abgeleiteten Daten den Cachecodec erweitern und
  dessen Version erhöhen.
- **Körperqualifizierte Ebene:** `sketch/planes.py`, `sketch/ops.py` und bestehende
  Referenz-Erfassung, soweit die aktuellen unqualifizierten Zielflächenwege
  sonst dieselbe Neuwahl am falschen Körper lesen würden.
- **Oberfläche/Agent:** `ui/session.py`, `dialogs.py`, `main_window.py`,
  `viewport.py`, gemeinsame Texte/alle Kataloge. Agent-Produktänderungen nur,
  wenn konkrete Anschlussfälle zeigen, dass der vorhandene gemeinsame Weg
  den neuen strukturierten Konflikt nicht transportiert; kein zweiter Solver.
- **Karten:** betroffene Bereichskarten; keine allgemeinen Architekturregeln
  duplizieren. Fensterdateien ausschließlich beim Release ausführen.

## 8. Unabhängige Sollfälle

1. Zwei native Stufen oder Bohrungen vertauschen ihre Erkennungsnamen; gespeicherte
   Folgereferenz darf die fremde gleichlautende Fläche nicht bedienen. Die
   bestätigte Neuwahl ändert nachweislich nur die gewählte Stelle.
2. Zwei symmetrische alte Ansprüche, ein nativer Nachfolger: vollständige Gruppe,
   höchstens eine Fortführung, kein Aliaszwilling, keine wiederbelebte verworfene ID.
3. Zwei Körper mit `face_1`: Frage, Preview, Skizzenrahmen, Passung und Folgebearbeitung
   verwenden ausschließlich den gewählten Körper. Alte unqualifizierte Zielfläche
   wird bei Konkurrenz nicht am ersten Objekt aufgelöst.
4. Eine planare Fläche wird nativ in zwei koplanare Flächen geteilt; vollständige
   Auswahl ist eine Menge. Ein nur teilweise umfasster nativer Träger wird nicht
   als ganze Fläche bearbeitet. Zusammengefasste Fläche öffnet konkurrierende
   alte Identitäten, auch wenn beide denselben Filamentslot hatten.
5. Native private Kopie mit geänderter Besuchsreihenfolge: gewählte Fläche/Kante
   folgt der echten Kopierabbildung. Originale Shape einschließlich bestehender
   Triangulation bleibt nach Erfolg, Fehler und Abbruch unverändert.
6. Press/Pull an zwei ähnlich gerichteten Stufen und Entfernen einer von mehreren
   Rundungen: ein ausdrücklich ausgewählter Träger erreicht den Builder direkt;
   eine absichtlich falsch gelegte Auswahlmitte darf keine andere Fläche gewinnen.
7. Zwei unterschiedliche Kanten mit demselben gerundeten Schlüssel: getrennte
   sichtbare Fragetoken, nur gewählte Kante bearbeitet, erneute echte Auflösung
   nach Öffnen. Sind alle gespeicherten Unterscheidungswerte gleich, bleibt die
   Wiederwahl offen. Ein fehlender Teil einer Mehrfachauswahl bearbeitet nichts.
8. Gezieltes `resize_hole` mit vorhandener Alias-/Bodenübernahme: Name, aktuelle
   Dreiecke, Maßquelle und Folge-Skizze bleiben korrekt, keine Doppelzuordnung
   durch den neuen allgemeinen nativen Abschluss.
9. Andere native Gruppenwahl bei identischem Rohkörper: Erzeuger darf Cachetreffer
   bleiben, Verbraucher muss neu rechnen; kalter/warm gespeicherter Lauf ergeben
   denselben unabhängigen Körper. Bindungsdigest und tatsächlicher Treffer werden
   ausdrücklich erfasst, nicht nur unterschiedliche Antwortdaten.
10. Save/load v27→v28, Undo/Redo, Antwortänderung, Kernwechsel und Scopeänderung:
    keine Migration erfindet native Zustimmung; geänderte Beteiligte oder
    ungeklärte Auswahl öffnen die Frage; native und Mesh-Antworten sind getrennt.
11. Abbruch nach erster Gruppenantwort, nach erster Körperausgabe, während
    Auswahlkopie und nach nativer Arbeit: Dokument, Antworten, Cache und
    ursprüngliche Körperbytes bleiben unverändert.
12. Agent und UI führen denselben Fall: offener Konflikt stoppt nachvollziehbar,
    vollständige Antwort führt als eine Transaktion zur tatsächlichen gewählten
    Geometrie. Die Fensterabnahme mit Hervorhebung, Tastatur und Rückweg bleibt
    ausdrücklich Release-Nachweis, kein aus Kernfällen abgeleitetes Grün.

Vor Umsetzung sollten die vorgeschlagenen neuen nativen Schlüsselräume samt
Scope und die getrennte Kantenfrage als Vertrag festgezogen werden. Kostenformel,
P1.4b-Gruppenschluss und Filamenthistorie werden dafür nicht umdefiniert.


