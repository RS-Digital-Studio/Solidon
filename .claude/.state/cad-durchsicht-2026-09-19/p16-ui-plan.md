# P1.6 — Ergänzungen für den Kundenweg

Lesende Anschlussprüfung des `p16-deviation-plan.md` am 20.09.2026. Grundlage:
CAD-Konzept §13.10/P1.6, Bauplan §18.4/§19.1 und die vorhandenen Kartenwege.
Diese Notiz ändert weder Produkt noch Tests; keine Fenster- oder Leistungsläufe.
Die laufenden P1.2/P1.3-Pakete bleiben eingefroren.

## Konkrete Deltas zum Messplan

1. **Ein Wähler, der ganze ausgewählte Körper.** `analysis_bar.py:57/267`
   führt `MAP_ORDER` und die beschriftete Eintragsliste getrennt; beide erhalten
   `deviation` samt Erklärung. `maps.py:289/329` erhält Titel und ausdrücklichen
   Zweig vor dem bisherigen `support`-Rückfall. Eine ausgewählte Bohrung darf
   die Körperkarte nicht unbemerkt auf dieses Merkmal beschränken. Der Bericht
   darf ein Merkmal fokussieren, der Umfang bleibt sichtbar der ganze Körper.
   Kein zusätzlicher Editor, kein neuer Werkzeugmodus, kein zusätzlicher Fit.

2. **Der Abbrechenknopf fehlt noch.** `_MapWorker` besitzt ein `CancelSignal`,
   aber `_analysis_map` zeigt lediglich `show_problem("… wird berechnet …")`;
   `_cancel_visible_progress` kennt keinen Kartenbesitzer. Den vorhandenen
   `_ProgressState` um diesen Besitzer und den bestehenden `_cancel_map_worker`
   als Handlung ergänzen, ohne zweite Fortschrittsleiste. Bei unbekannter Dauer
   unbestimmter Balken, keine erfundenen Prozentwerte. Karten-/Körperwechsel,
   „Keine Karte“ und Fensterende entwerten dieselbe Anfrage. Abschluss, Abbruch
   und Fehler räumen nur ihren eigenen Fortschritt. Kein späteres Teilergebnis.

3. **Unbekannt ist keine Null.** `_legend_entries` (`analysis_bar.py:211`)
   erzeugt derzeit auch bei ausschließlich `NaN` und `low=high=0` ein Zahlenfeld.
   Für eine durchgehend unbekannte Karte keine numerische Rampe und keinen
   Maximalwert zeichnen; die Karte mit Grund und unverändert bedienbarem Wähler
   behalten. Teilkarten zeigen „Ausgewertete Dreiecksflächen: … von …“ sowie den
   unbekannten Anteil. Vorhandenes `NaN` und `CellColours.nan_colour` verwenden
   (`render/gfx_renderer.py:209–219`), keine neue Palette. Die lesbare Auskunft
   neben der Karte bleibt die zweite Kodierung. Nur endliche, gültige Werte
   dürfen den Kernvertrag `AnalysisMap.known` erreichen; Inf ist kein Messwert.

4. **Die wirklichen Bezugsflächen benennen.** `source="internal"` beschreibt
   die Rechenherkunft, keine geometrische Genauigkeit. Die vorhandenen
   `note`/`unknown_note` aus den tatsächlich verwendeten Teilträgern füllen:
   `native`, `fit` oder gemischt. Weder `SceneObject.kind` noch
   `provenance="detected"` genügt dafür. Auch ein exakter Körper kann nur für
   einen Teil seiner Flächen belegte native Bezüge liefern. Beim nativen Bezug
   wird die Dreiecksdarstellung geprüft; beim Fit die Abweichung zur erkannten
   Form. Beides belegt keine ursprünglichen Sollmaße oder Fertigungstoleranz.

5. **Rechenschranke und Raster getrennt halten.** `AnalysisMap.resolution`
   (`maps.py:156`) bleibt ausschließlich Rasterweite. Falls der Rechner
   Obergrenzen statt geschlossener Maximalwerte liefert, braucht `AnalysisMap`
   ein ausdrücklich benanntes optionales Ergebnisfeld für diese numerische
   Schranke. Die Legende sagt dann „Obergrenzen je Dreiecksfläche“ und nennt
   das vom Kern gelieferte globale Intervall. Kein stilles „±“, kein
   Genauigkeitsversprechen aus `EPS_DISPLAY`, Materialspiel oder Fitresidual.
   Farben ab null sind eine Skala, keine Behauptung, tatsächlich eine
   Nullabweichung gemessen zu haben. Alle Aussagen zum Maximum beziehen sich
   nur auf die ausgewerteten Flächen, solange andere unbekannt bleiben.

6. **Eine gemeinsame Längenformatierung.** `labels.length` verwendet
   `units.format_length`, das kleine positive Werte derzeit auf null runden
   kann. Den vorhandenen Formatierungsweg mit dem Muster `_format_with_bound`
   (`units.py:274`) eng ergänzen: kleiner positiver Wert als Schranke oder mit
   tragfähiger Präzision, niemals als Nullnachweis. Untere Intervallgrenzen nach
   unten, obere nach oben runden; gewöhnliches Runden kann aus einer gültigen
   Obergrenze eine falsche machen. Die bereits formatierten Platzhalter tragen
   ihre Anzeigeeinheit. Keine fest angehängten „mm“ in Legende, Hinweis oder
   Ortsmarke. Der aktuelle Weg `set_display_unit → _on_selection →
   _on_map_changed` zeichnet eine gültige gecachte Karte bereits neu; diesen
   Anschluss verwenden, keine zweite Datenhaltung und keine Neuberechnung
   allein beim Wechsel zwischen Millimetern und Zoll.

7. **Berichtsklick wirklich an seinen Auftrag binden.** Der Verfügbarkeitsbefund
   braucht einen tatsächlichen Erzeuger, `info` und Körperbezug; er behauptet
   noch keinen Maximalwert. Sein Code kommt in `map_for` vor `perceive.*`.
   `_on_finding_activated` wählt derzeit erst nach `_analysis_map` den Körper;
   dessen Auswahlereignis kann die erste Anfrage wieder ersetzen. Für den neuen
   Weg zuerst den Körper binden, dann dieselbe Karte anfordern. Alte Ortsmarke
   sofort entfernen. `_finding_awaiting_map` hält heute nur den Befund;
   `_map_ready:11577–11587` kann ihn ohne Prüfung seines Karten-/Körperbezugs
   übernehmen. Diesen bestehenden wartenden Zustand an Befund, Anfrage,
   Körper, Kartenart und Ergebnisstand binden. Jeder andere Berichtsklick,
   Kartenwechsel, Abbruch und Dokumentwechsel verwirft ihn. Kein zweiter Worker.

8. **Ein tatsächlicher Zeugenpunkt.** `location_of` und `focus_point`
   (`maps.py:1116–1157`) mitteln Dreiecksschwerpunkte. Der neue Befund darf
   diesen Rückfall weder vor noch nach der Rechnung verwenden. Der Kern liefert
   mit `AnalysisMap` den echten Punkt auf einem ausgewerteten Dreieck und den
   dort bestimmten Abstand; gegebenenfalls auch den zugehörigen Merkmalbezug.
   Bei mehreren gleich großen Maxima einen wirklichen Punkt deterministisch
   wählen, niemals deren Mittel im Hohlraum. Bei numerischer Eingrenzung ist
   dieser Punkt ein Zeuge der unteren Schranke; die obere Schranke hat nicht
   automatisch einen realisierten Ort. Seine Marke heißt deshalb dann „Größter
   gefundener Abstand“, nicht „hier liegt die Obergrenze“. Erst das gültige
   Ergebnis startet `_show_finding_at`; der vorhandene Viewport erhält die Marke
   über seinen asynchronen Szenenneuaufbau. Ein vollständig unbekanntes oder
   punktloses Ergebnis lässt nur die Körperauswahl stehen. Auch ein solcher
   Cachetreffer beendet das Warten sofort, statt einen nicht laufenden Worker
   vorauszusetzen. Die Umrechnung von Szene zu Platte/Explosionsansicht bleibt
   allein in `_show_finding_at`/`viewport.view_point_of`.

9. **Abbruchgrund auf die richtige Karte beziehen.** `_map_timed_out`
   (`main_window.py:11542`) und `MapBudgetExceeded` nennen heute ausdrücklich
   die Stützkarte. Falls P1.6 diesen Budgetweg verwendet, den vorhandenen
   Fehler-/Workerweg um den betroffenen Kartentitel erweitern. Keine zweite
   Budgetverwaltung. „Dreiecke verringern“ verändert den zu prüfenden Körper;
   es darf für P1.6 keine automatische Abhilfe oder Behauptung über das Original
   sein. Der bestehende Wähler beziehungsweise `show_problem` führt zu
   „Keine Karte“/einem anderen Körper. Eine ausdrücklich gewählte
   Dezimierungsoperation bleibt ein anderer Dokumentstand mit neuer Karte.

## Kleiner gemeinsamer Ergebnisvertrag

`AnalysisMap.values`, `unit`, `low/high`, `known`, `unknown_count`, `note`,
`unknown_note` und die bestehende Farbraumabbildung weiterverwenden. Neu nötig
sind nur die optionalen Daten für **numerische Eingrenzung** und
**Zeugenpunkt samt dortigem Wert**; ihre konkreten Feldnamen mit dem Kartenkern
festlegen. Intervallenden und Ortswerte entstehen dort, nicht in der Oberfläche.
Eine obere Facettengrenze darf nicht als am Zeugenpunkt gemessener Abstand
erscheinen. `resolution` bleibt davon unabhängig. Der Kern liefert weiterhin
genau einen Eintrag je ursprünglichem Dreieck, ohne neues Remeshing.

Zwei Kundenwege: Körper → Analyse → Formabweichung; oder echte Berichtszeile →
derselbe Wähler und Körper → gültige Karte → gegebenenfalls Ortsmarke. Beim
kalten Cache wartet nur die Auskunft, bei gültigem warmem Cache erfolgt dieselbe
Ausgabe sofort. Ein Abbruch oder ein neuer Stand entfernt die veraltete Auskunft.

Vor Umsetzung gezielte Kernfälle in `test_maps.py`/`test_map_display_scale.py`
für unbekannte Karten, Schranken und wirkliche Zeugen; Formatierungsfälle im
vorhandenen Einheitentest. Die bestehenden Fensterfälle in
`test_analysis_ui.py` um vollständige/teilweise Unbekanntheit, zwei
gegenüberliegende Maxima, kleinen positiven Abstand, mm/Zoll, leeren/warmen
Cache und überholte Anfrage erweitern. Fensterfälle ausschließlich beim Release
ausführen. Diese Notiz ist kein Nachweis einer ausgeführten Abnahme.

## Deutsche Quellen und fünf Sprachfassungen

Entwurf für die spätere Umsetzung, noch keine Katalogänderung. Die Kennungen
sind nur Referenzen dieser Notiz. `{value}`, `{lower}`, `{upper}` und `{bound}`
enthalten bereits lokalisierte Längen samt Einheit; Zahlen nicht im Text doppelt
formatieren. `{known}`/`{total}` sind Anzahlen, `{seconds}` ist lokalisiert.
Quellenhinweise gehören kurz in `note`, die Erläuterung zusätzlich in Tooltip,
Statushinweis und `accessibleDescription`. Nur auf den jeweiligen Fall zutreffende
Texte zeigen; nicht sämtliche Hinweise nebeneinander stapeln.

```yaml
title:
  de: Formabweichung
  en: Shape deviation
  es: Desviación de forma
  fr: Écart de forme
  it: Scostamento di forma
  pt: Desvio de forma
choice_help:
  de: Zeigt den größten Abstand jeder kleinen Dreiecksfläche zur zugeordneten Form.
  en: Shows the greatest distance from each small triangular face to its reference shape.
  es: Muestra la mayor distancia de cada pequeña cara triangular a su forma de referencia.
  fr: Montre la plus grande distance entre chaque petite face triangulaire et sa forme de référence.
  it: Mostra la distanza massima di ogni piccola faccia triangolare dalla sua forma di riferimento.
  pt: Mostra a maior distância de cada pequena face triangular à sua forma de referência.
coverage:
  de: 'Ausgewertete Dreiecksflächen: {known} von {total}'
  en: 'Triangular faces evaluated: {known} of {total}'
  es: 'Caras triangulares evaluadas: {known} de {total}'
  fr: 'Faces triangulaires évaluées : {known} sur {total}'
  it: 'Facce triangolari valutate: {known} su {total}'
  pt: 'Faces triangulares avaliadas: {known} de {total}'
unknown_reason:
  de: Keine Form sicher zugeordnet
  en: No reliably assigned reference shape
  es: No hay una forma de referencia asignada con certeza
  fr: Aucune forme de référence attribuée avec certitude
  it: Nessuna forma di riferimento assegnata con certezza
  pt: Nenhuma forma de referência atribuída com segurança
all_unknown:
  de: Keine Abweichungswerte bestimmbar. Wählen Sie einen anderen Körper.
  en: No deviation values could be determined. Select another body.
  es: No se pudieron determinar valores de desviación. Seleccione otro cuerpo.
  fr: Aucune valeur d’écart n’a pu être déterminée. Sélectionnez un autre corps.
  it: Non è stato possibile determinare valori di scostamento. Selezionare un altro corpo.
  pt: Não foi possível determinar valores de desvio. Selecione outro corpo.
fit_reference:
  de: 'Bezug: erkannte Form. Die ursprünglichen Sollmaße sind damit nicht belegt.'
  en: 'Reference: detected shape. This does not establish the original intended dimensions.'
  es: 'Referencia: forma detectada. Esto no permite confirmar las dimensiones originales previstas.'
  fr: 'Référence : forme détectée. Cela ne permet pas de confirmer les dimensions prévues à l’origine.'
  it: 'Riferimento: forma rilevata. Questo non conferma le dimensioni originariamente previste.'
  pt: 'Referência: forma detetada. Isto não confirma as dimensões originalmente previstas.'
native_reference:
  de: 'Bezug: exakte Fläche. Die Karte prüft die Dreiecksdarstellung des Körpers.'
  en: 'Reference: exact surface. The map checks the triangular representation of the body.'
  es: 'Referencia: superficie exacta. El mapa comprueba la representación triangular del cuerpo.'
  fr: 'Référence : surface exacte. La carte vérifie la représentation triangulaire du corps.'
  it: 'Riferimento: superficie esatta. La mappa verifica la rappresentazione triangolare del corpo.'
  pt: 'Referência: superfície exata. O mapa verifica a representação triangular do corpo.'
mixed_reference:
  de: 'Bezug: exakte und erkannte Flächen.'
  en: 'Reference: exact and detected surfaces.'
  es: 'Referencia: superficies exactas y detectadas.'
  fr: 'Référence : surfaces exactes et détectées.'
  it: 'Riferimento: superfici esatte e rilevate.'
  pt: 'Referência: superfícies exatas e detetadas.'
maximum:
  de: 'Größter Abstand: {value}'
  en: 'Greatest distance: {value}'
  es: 'Mayor distancia: {value}'
  fr: 'Plus grande distance : {value}'
  it: 'Distanza massima: {value}'
  pt: 'Maior distância: {value}'
upper_values:
  de: Obergrenzen je Dreiecksfläche
  en: Upper bounds for each triangular face
  es: Límites superiores por cara triangular
  fr: Bornes supérieures par face triangulaire
  it: Limiti superiori per ogni faccia triangolare
  pt: Limites superiores por face triangular
maximum_interval:
  de: 'Größter Abstand: {lower} bis {upper}'
  en: 'Greatest distance: {lower} to {upper}'
  es: 'Mayor distancia: de {lower} a {upper}'
  fr: 'Plus grande distance : de {lower} à {upper}'
  it: 'Distanza massima: da {lower} a {upper}'
  pt: 'Maior distância: de {lower} a {upper}'
numerical_bound:
  de: 'Breite des berechneten Intervalls: höchstens {bound}'
  en: 'Width of the computed interval: at most {bound}'
  es: 'Anchura del intervalo calculado: como máximo {bound}'
  fr: 'Largeur de l’intervalle calculé : au plus {bound}'
  it: 'Ampiezza dell’intervallo calcolato: al massimo {bound}'
  pt: 'Largura do intervalo calculado: no máximo {bound}'
numerical_help:
  de: Die Breite des Intervalls beschreibt nur, wie genau der Abstand berechnet wurde. Sie ist keine Fertigungstoleranz.
  en: The interval width only describes how accurately the distance was computed. It is not a manufacturing tolerance.
  es: La anchura del intervalo solo indica con qué precisión se calculó la distancia. No es una tolerancia de fabricación.
  fr: La largeur de l’intervalle décrit uniquement la précision du calcul de la distance. Ce n’est pas une tolérance de fabrication.
  it: L’ampiezza dell’intervallo descrive solo la precisione con cui è stata calcolata la distanza. Non è una tolleranza di fabbricazione.
  pt: A largura do intervalo descreve apenas a precisão com que a distância foi calculada. Não é uma tolerância de fabrico.
witness:
  de: 'Größter gefundener Abstand: {value}'
  en: 'Greatest distance found: {value}'
  es: 'Mayor distancia encontrada: {value}'
  fr: 'Plus grande distance trouvée : {value}'
  it: 'Distanza massima trovata: {value}'
  pt: 'Maior distância encontrada: {value}'
available:
  de: Formabweichung ist für diesen Körper verfügbar.
  en: Shape deviation is available for this body.
  es: La desviación de forma está disponible para este cuerpo.
  fr: L’écart de forme peut être affiché pour ce corps.
  it: Lo scostamento di forma è disponibile per questo corpo.
  pt: O desvio de forma está disponível para este corpo.
show:
  de: Formabweichung anzeigen
  en: Show shape deviation
  es: Mostrar desviación de forma
  fr: Afficher l’écart de forme
  it: Mostrare lo scostamento di forma
  pt: Mostrar desvio de forma
timed_out:
  de: 'Die Karte „{name}“ wurde nach {seconds} Sekunden beendet. Wählen Sie einen anderen Körper oder schließen Sie die Karte.'
  en: 'The “{name}” map calculation stopped after {seconds} seconds. Select another body or close the map.'
  es: 'El cálculo del mapa «{name}» se detuvo después de {seconds} segundos. Seleccione otro cuerpo o cierre el mapa.'
  fr: 'Le calcul de la carte « {name} » s’est arrêté après {seconds} secondes. Sélectionnez un autre corps ou fermez la carte.'
  it: 'Il calcolo della mappa «{name}» si è interrotto dopo {seconds} secondi. Selezionare un altro corpo o chiudere la mappa.'
  pt: 'O cálculo do mapa «{name}» parou após {seconds} segundos. Selecione outro corpo ou feche o mapa.'
cancelled:
  de: Die Berechnung der Analysekarte wurde abgebrochen.
  en: The analysis map calculation was cancelled.
  es: Se canceló el cálculo del mapa de análisis.
  fr: Le calcul de la carte d’analyse a été annulé.
  it: Il calcolo della mappa di analisi è stato annullato.
  pt: O cálculo do mapa de análise foi cancelado.
```

Vorhandene Quellen wiederverwenden: „Keine Karte“, „Analysekarte“, „Herkunft“,
„nicht bestimmbar“, „Die Analysekarte wird berechnet …“ und die generische
Dreiecksgrenzenmeldung. Zahlen, Ursprungsangaben und Tooltip stammen jeweils
aus demselben Kartenergebnis. Der Quelltextentwurf trifft keine neue Aussage
über die erreichte Rechengenauigkeit oder ein bestandenes Leistungsbudget.
