# KI-Transparenz und KI-Kompetenz — Solidon

Stand: 31. August 2026 · Prozessfassung 1.0

**Freigabestatus: GESPERRT.** Der KI-Chat darf erst freigegeben werden, wenn
die Offenlegung vor der ersten Modellkommunikation in allen sechs Sprachen und
für Anthropic wie Ollama getestet ist. Die Konstruktionsanwendung ohne Chat
bleibt davon unabhängig nutzbar.

## Einheitliche Offenlegung

Vor der ersten Nachricht an ein Modell zeigt Solidon gut wahrnehmbar und
barrierefrei mindestens:

**Dialogtitel:** „Interaktion mit einem KI-System“

> Sie interagieren mit einem KI-System. Antworten können falsch oder
> unvollständig sein. Solidon führt daraus keine Geometrie ungeprüft aus: Ein
> Vorschlag bleibt sichtbar, prüfbar und mit einem Schritt rücknehmbar.

Für Anthropic kommt vor dem Senden hinzu:

> Wenn Sie Anthropic wählen, werden Ihre Chatnachricht und die zuvor angezeigte
> Projektauswahl direkt an Anthropic übertragen. Verwenden Sie Ihren eigenen
> API-Schlüssel. Ohne Ihre ausdrückliche Auswahl werden keine Projektdatei und
> kein Vorschaubild übertragen.

Für Ollama kommt hinzu:

> Wenn Sie Ollama wählen, verarbeitet das ausgewählte lokale Modell die
> Nachricht auf diesem Rechner. Installations-, Download- oder Updatewege des
> Modells können gesondert eine Netzverbindung verwenden.

Die Anzeige ist Information, keine versteckte Einwilligung und keine
Haftungsfreizeichnung. Sie erscheint vor dem ersten Senden, nicht erst in
Einstellungen oder Handbuch. Tastatur, Bildschirmleser, Zoom, schmale Fenster
und alle Sprachkataloge werden geprüft.

Die primäre Handlung heißt „Verstanden und fortfahren“, die zweite „Zurück“.
„Zurück“, Escape, Fensterschließen und jeder Darstellungsfehler senden nichts.
Die primäre Handlung wird erst aktiv, nachdem Titel, allgemeiner Hinweis und
der zum ausgewählten Backend gehörende Abschnitt zugänglich angezeigt wurden.

## Nachweis und Zustandsmodell

Gespeichert werden ausschließlich Version und Zeitpunkt der angezeigten
Offenlegung sowie der gewählte Backend-Typ. Eine erneute Anzeige ist nötig,
wenn sich Datenarten, Empfänger, Zweck, Anbieterrolle oder Textversion ändern.
Der Zustand ist kein Konto, wird nicht zu Telemetrie und reist nicht in einer
Projektdatei. Ein Zurücksetzen in den Einstellungen ist möglich.

Die Anwendung verhindert den ersten Modellaufruf technisch, solange die
aktuelle Offenlegung nicht vollständig angezeigt wurde. Abbruch oder
Barrierefreiheitsfehler führt zurück zur Backend-Auswahl und sendet nichts.

## Rollen und Ausgaben

Die private Rollenakte bestimmt je Weg Anbieter, Betreiber, Nutzer,
Verantwortlichen/Auftragsverarbeiter und Empfänger. Ein eigener API-Schlüssel
oder ein lokales Modell entscheidet diese Rollen nicht automatisch.

Gespeicherter Chat und daraus erzeugte Vorschläge tragen Provenienz: Backend,
Modellkennung, Zeitpunkt und Kennzeichnung als KI-Ausgabe. Exporte von Text
und anderen erfassten synthetischen Inhalten werden gegen Art. 50 Abs. 2 der
Verordnung (EU) 2024/1689 und die Übergangsregel bis 2. Dezember 2026 geprüft.
Für 3D-Geometrie wird weder eine Pflicht noch eine Ausnahme ohne fachliche
Einordnung behauptet.

## Grenzen des Agenten

- Kein Modellcode oder fremder Quelltext wird ausgeführt.
- Werkzeuge folgen festen Schemata, Grenzen und einem nachvollziehbaren
  Operationsregister.
- Fremde Katalog-, Projekt- und Provenienztexte sind untrusted data und keine
  Systemanweisung.
- Mehrdeutigkeit hält an und fragt; ein Vorschlag ist genau eine rücknehmbare
  Transaktion.
- Sicherheits- und Druckbarkeitsprüfung bleibt Code; KI-Antworten sind keine
  Freigabe eines realen Bauteils.

## KI-Kompetenz nach Art. 4

Mindestens jährlich und bei wesentlichen Änderungen wird für alle Personen,
die KI-Auswahl, Prompt, Werkzeuge, Freigabe oder Support beeinflussen,
dokumentiert:

1. Modell- und Datenflussgrenzen,
2. Halluzination, Prompt-Injection und Toolmissbrauch,
3. Datenschutz, Geheimnisse und Drittlandtransfer,
4. menschliche Prüfung, Rücknahme und Eskalation,
5. Incident Handling und Änderungsfreigabe,
6. Datum, Teilnehmer, Material und Verständnisnachweis.

## Freigabekriterien und Handoff

- [ ] Offenlegung vor dem ersten Anthropic- und Ollama-Aufruf erzwungen,
- [ ] Texte in Deutsch, Englisch, Spanisch, Französisch, Italienisch und
      Portugiesisch vollständig,
- [ ] Tastatur-/Screenreader-/Abbruchtests bestanden,
- [ ] Cloud-Nutzlastvorschau und aktuelle Anbieter-/Datenschutzlinks vorhanden,
- [ ] versionierter Anzeigenachweis ohne Projekt-/Telemetriedaten,
- [ ] Rollenakte und Art.-50-Abs.-2-Entscheidung fachlich bestätigt,
- [ ] KI-Kompetenznachweis vorhanden.

UI-Handoff: Eigentümer sind Einrichtungsdialog/Backend-Auswahl und die
Chat-Sendegrenze. Der Test muss den tatsächlichen ersten Netzwerk- oder lokalen
Modellaufruf beobachten; ein vorhandener Textschlüssel allein ist kein
Nachweis.
