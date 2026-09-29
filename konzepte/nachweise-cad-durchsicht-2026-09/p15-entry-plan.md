# P1.5 – Anschluss nach dem Zuordnungspaket

Lesender Einstieg während der P1.4-Umsetzung. Keine Produktänderung und kein
Nachweis einer vollständig erfüllten P1.5-Abnahme.

## Vorhandene gemeinsame Auskünfte

- `Feature` trägt Art, Parameter, Originaldreiecke, Erzeuger, Maßquellen und
  akzeptierte analytische `surface_patches`. P1.2/P1.6 haben diese Angaben
  bereits durch Transformation, Erkennung, Cache, Maße und Analysekarte geführt.
- `perceive.relations` bildet Hohlraumketten, Rohrwände und die belegten
  Sammelgruppen `FeatureActionGroup` einschließlich `scope`, `evidence` und
  `uncertain`. Die Paketkarte erklärt die einseitige Abhängigkeit von der
  Formwahrnehmung. Ein weiterer parallel gepflegter Gruppenvertrag wäre ein
  fachlicher Zwilling.
- `brep.features.features_of` liest native Träger und Materialseite, verbindet
  Langlöcher und Ringstücke, nutzt für angeschnittene Öffnungen bereits die
  gemeinsame Netzregel, ergänzt Restflächen und abgeschlossene Innenräume.
  Native Träger haben beim abschließenden Zuschneiden Vorrang vor Netzfits.
- Auswahl, Agent und Bearbeitung lesen schon `actions` und `relations`;
  vollständige Parität folgt daraus noch nicht. Vor allem die tatsächliche
  Körpergrenze und vollständig gemeinsame Randketten sind am jeweiligen
  Erzeugungspfad zu belegen.

## Nächster prüfbarer Umfang

1. Dieselben konstruierten Sollkörper als native Formen und als verschieden
   tessellierte Netze aufbauen: Bohrung mit Senkung/Schulter, blind/durchgehend,
   angeschnittener Zylinder, offenes/geschlossenes Langloch, kreuzende und
   überlappende Höhlungen, echte kleine Flächen neben großen Nachbarn.
2. Je Fall explizit Form, gemessene Größen, Herkunft, Originalflächenanteil,
   Innen-/Außenrolle, Öffnung und zulässige Handlung prüfen. Vorhandene
   Flächen-/Gruppentests zuerst wiederverwenden. Eine gleiche Anzahl oder
   gleiches Volumen allein beweist keine Parität.
3. Fehlende und widersprüchliche Belege am gemeinsamen Verbraucherweg
   festhalten. Getrennte Höhlungen dürfen durch ähnliche Achsen keine Kette
   werden; tatsächliche Berührung darf keinen sicheren Einzelteilumfang
   vortäuschen. Noch unbekannte Bereiche bleiben als solche erkennbar.
4. Erst aus den Gegenfällen den nötigen Vertragsausbau ableiten. Vorhandene
   `Feature`, `SurfacePatch` und `FeatureActionGroup` erweitern, soweit deren
   Fragen passen; keinen zweiten Erkenner oder zweiten Maßsatz daneben bauen.
5. Von den korrigierten Kernauskünften aus die echten Auswahl-/Maß-/Agenten-
   und Operationsaufrufer durchgehen, Speicherung und Abbruch mitnehmen.
   Statische UI-Vertragsprüfung während der Entwicklung; sämtliche
   Fensterdateien und eigentliche Kundenabnahme erst beim Release.

## Offene Grenzfragen

Die Testwürfel für P1.4 mussten auf Kantenlänge 2 mm vergrößert werden:
`perceive.features.MIN_FACE_AREA = 4.0` verwirft 1-mm²-Flächen, während der
native Weg sie erkennt. Das ist ein belegter Unterschied und für P1.5
gesondert gegen die Forderung nach kleinen echten Merkmalen zu beurteilen,
keine Erlaubnis, im Zuordnungspaket die Erkennungsschwelle zu ändern.

Der native Zweig verwendet für offene Rundmäntel weiterhin `fit_cylinder`
und `open_slots_instead_of_fillets` über die aktuelle Tessellierung. Zu prüfen
ist, ob Umfang und Maßquelle dabei nativ belegt bleiben oder ob die Ausgabe
zu Recht als Fit ausgewiesen werden muss; keine pauschale Hochstufung.

Die Erhöhung von `FEATURE_LIMIT_COUNT` bleibt unabhängig beim Release.
`relations._Measured` begründet sein Paarbudget noch ausdrücklich mit der
Tausendergrenze. Eine funktionale Verbesserung von `matching` ersetzt die
Abnahme der übrigen Verbraucher und der dichten Gegenfälle nicht.
