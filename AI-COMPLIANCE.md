# KI-Transparenz und KI-Kompetenz — Solidon

Stand: 12. September 2026 · Prozessfassung 1.2

**Prüfstatus: Technische Teilnachweise vorhanden, Gesamtfreigabe offen.**
Der KI-Chat ist in der öffentlichen Demo bereits verfügbar. Seine Sendegrenze
und die Ollama-Werkzeugprobe verwenden `ensure_ai_disclosure()`; gezielte
Tests belegen Abbruch, Fortfahren, Zielbindung und den versionierten Nachweis.
Die Texte für Anthropic sowie lokales und entferntes Ollama liegen in allen
sechs Sprachen vor. Das belegt weder die vollständige Barrierefreiheitsabnahme
noch Rollenprüfung, Ausgabekennzeichnung oder KI-Kompetenz.

Weg 3 (Bild-/Texterzeugung über ComfyUI) hat einen eigenen technischen
Teilnachweis. Sein Hinweis nennt Beschreibung oder Bilddatei, Startwert,
Erzeugungsablauf und Modellwahl sowie das lokale oder entfernte Ziel. Tests
beobachten den tatsächlichen Generatoraufruf: Abbruch, Zielwechsel und ein
fehlgeschlagener Speichervorgang verhindern ihn; erst der angezeigte und
gespeicherte Hinweis lässt ihn zu (F-U6-4).
Offene Kriterien unten bezeichnen fehlende Nachweise; die Verfügbarkeit eines
Wegs ist keine rechtliche oder betriebliche Freigabe.

## Einheitliche Offenlegung

Der folgende Offenlegungsvertrag gilt für den KI-Chat und die
Ollama-Werkzeugprobe. Vor der ersten Nachricht zeigt Solidon gut wahrnehmbar
und barrierefrei mindestens:

**Dialogtitel:** „Interaktion mit einem KI-System“

> Sie interagieren mit einem KI-System. Antworten können falsch oder
> unvollständig sein. Solidon führt daraus keine Geometrie ungeprüft aus: Ein
> Vorschlag bleibt sichtbar, prüfbar und mit einem Schritt rücknehmbar.

Für Anthropic kommt vor dem Senden hinzu:

> Wenn Sie Anthropic wählen, werden Ihre Chatnachricht und die zuvor angezeigte
> Projektauswahl nicht allein übertragen. Direkt an Anthropic gehen die
> aktuelle Nachricht, bis zu zwölf frühere Chatbeiträge, ein textlicher
> Steckbrief der gesamten aktuellen Szene mit Objekt- und Quellnamen, Maßen,
> Merkmalen, Parametern, Einstellungen und Auswahl, der Prüfbericht sowie die
> für den Agenten nötigen Anweisungen, Regeln und Werkzeugschemata. Unterstützt
> das gewählte Modell Bilder, kann Solidon außerdem automatisch gerenderte
> Ansichten der Szene mitsenden. Die Projektdatei und die Netzgeometrie selbst
> werden nicht übertragen. Sie verwenden Ihren eigenen API-Schlüssel.

Für Ollama nennt die Anzeige die normalisierte, von Zugangsdaten, Pfad,
Abfrage und Fragment bereinigte Zieladresse und unterscheidet zwei Fälle.

**Lokales Ollama-Ziel (Loopback):**

> Das Ollama-Modell verarbeitet auf diesem Rechner dieselben Arbeitsdaten wie
> der Chat: aktuelle Nachricht, bis zu zwölf frühere Chatbeiträge, textlichen
> Steckbrief der gesamten Szene, Prüfbericht, Anweisungen, Regeln und
> Werkzeugschemata sowie bei einem Bildmodell automatisch gerenderte Ansichten.
> Projektdatei und Netzgeometrie selbst werden nicht übertragen. Die
> Werkzeugprobe sendet nur einen festen technischen Prüfauftrag ohne Projekt-
> oder Chatinhalt. Installation, Download oder Update des Modells können
> gesondert eine Netzverbindung verwenden.

**Entferntes Ollama-Ziel:**

> Das Ollama-Ziel liegt auf einem anderen Rechner. An die angezeigte Adresse
> werden aktuelle Nachricht, bis zu zwölf frühere Chatbeiträge, der textliche
> Steckbrief der gesamten Szene, Prüfbericht, Anweisungen, Regeln und
> Werkzeugschemata sowie bei einem Bildmodell automatisch gerenderte Ansichten
> übertragen. Projektdatei und Netzgeometrie selbst werden nicht übertragen.
> Die Werkzeugprobe sendet einen festen technischen Prüfauftrag. Verwenden Sie
> nur ein Ziel, dessen Betreiber und Übertragungsweg Sie vertrauen.

Der Cloud-Hinweis muss alle tatsächlich gesendeten Datenarten nennen; eine
pauschale „Chatnachricht“- oder „Projektauswahl“-Beschreibung genügt nicht.
Ändert sich `build_messages()`, die automatische Ansichtserzeugung, die
Werkzeugprobe, die Ollama-Zielklasse oder deren normalisierte Adresse, ist das
eine disclosure-relevante Änderung und sperrt den ersten Modellaufruf bis
Textversion, Kataloge und Tests nachgezogen sind. Ein Wechsel von lokal zu
entfernt oder zwischen entfernten Hosts übernimmt nie den alten Nachweis.

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
Offenlegung, der gewählte Backend-Typ und die normalisierte Zieladresse.
Der Erzeuger führt seinen eigenen Nachweis samt Datenumfangskennung; ein
Chatnachweis ersetzt ihn nicht. Eine erneute Anzeige ist nötig,
wenn sich Datenarten, Empfänger, Zweck, Anbieterrolle oder Textversion ändern.
Der Zustand ist kein Konto, wird nicht zu Telemetrie und reist nicht in einer
Projektdatei. Ein Zurücksetzen in den Einstellungen ist möglich.

Die Chat-Sendegrenze und die Ollama-Werkzeugprobe verhindern den ersten
Modellaufruf technisch, solange die aktuelle Offenlegung nicht vollständig
angezeigt wurde. Abbruch oder
Barrierefreiheitsfehler führt zurück zur Backend-Auswahl und sendet nichts.

## Rollen und Ausgaben

Die private Rollenakte bestimmt je Weg Anbieter, Betreiber, Nutzer,
Verantwortlichen/Auftragsverarbeiter und Empfänger. Ein eigener API-Schlüssel
oder ein lokales Modell entscheidet diese Rollen nicht automatisch.

Gespeicherter Chat und daraus erzeugte Vorschläge tragen Provenienz: Backend,
Modellkennung, Zeitpunkt und Kennzeichnung als KI-Ausgabe. Exporte von Text
und anderen erfassten synthetischen Inhalten werden gegen Art. 50 Abs. 2 der
Verordnung (EU) 2024/1689 geprüft. Die Übergangsfrist in Art. 111 Abs. 4 bis
2. Dezember 2026 betrifft nur erfasste KI-Systeme, die vor dem 2. August 2026
in Verkehr gebracht wurden; sie wird für Solidon nicht ohne passenden Beleg
in Anspruch genommen. Für 3D-Geometrie wird weder eine Pflicht noch eine
Ausnahme ohne fachliche Einordnung behauptet.
Quelle, geprüft am 12. September 2026:
[KI-Verordnung, konsolidierte Fassung vom 27. Juli 2026, Art. 4, 50, 111 und 113](https://eur-lex.europa.eu/legal-content/DE/TXT/?uri=CELEX:02024R1689-20260727).

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

- [x] Offenlegung vor dem ersten Chat-Aufruf an Anthropic oder Ollama und
      vor der Ollama-Werkzeugprobe erzwungen; Abbruch und Zielbindung geprüft,
- [x] Chat-/Werkzeugproben-Texte für alle drei Zielklassen in Deutsch, Englisch,
      Spanisch, Französisch, Italienisch und Portugiesisch vollständig,
- [x] Weg 3: eigene Offenlegung für Beschreibung oder Bilddatei, Startwert,
      Erzeugungsablauf und Modellwahl;
      Loopback/Remote-Ziel, Zielwechsel, Abbruch und erste Übermittlung geprüft,
- [ ] Tastatur-/Screenreader-/Abbruchtests bestanden,
- [ ] Cloud-Nutzlastvorschau und aktuelle Anbieter-/Datenschutzlinks vorhanden,
- [x] versionierter Chat-Anzeigenachweis mit Backend, normalisiertem Ziel und
      UTC-Zeitpunkt ohne Projekt-/Telemetriedaten,
- [ ] Rollenakte und Art.-50-Abs.-2-Entscheidung fachlich bestätigt,
- [ ] KI-Kompetenznachweis vorhanden.

Die abgehakten technischen Kriterien sind durch die gezielten Prüfungen
`test_the_record_binds_version_backend_target_and_a_real_utc_timestamp`,
`test_every_catalog_translates_all_three_target_paths_and_actions`,
`test_back_blocks_the_actual_first_chat_call_and_restores_every_character`,
`test_accepting_sends_exactly_once_and_the_same_target_needs_no_repeat` und
`test_tool_probe_is_gated_and_uses_the_exact_disclosed_remote_target` in
`tests/test_ai_disclosure.py` belegt. Für Weg 3 belegen dort die Prüfungen
`test_comfy_record_is_separate_and_invalidates_each_contract_field` und
`test_comfy_notice_translations_fit_at_large_text` den eigenen Nachweis und
die übersetzte Anzeige. In `tests/test_generate_ui.py` beobachten
`test_comfy_disclosure_blocks_the_actual_generator` und
`test_comfy_sends_only_after_the_separate_notice_and_reuses_its_record` die
Sendegrenze für Text und Bild an lokale und entfernte Ziele. Diese gezielten
Prüfungen sind keine Gesamtfreigabe der Akte.

UI-Handoff: Eigentümer sind Einrichtungsdialog/Backend-Auswahl,
Chat-Sendegrenze und für Weg 3 `GenerateDialog._start`. Der Erzeuger übernimmt
keinen Chat-Merker; sein Nachweis ist an Datenarten, Textversion und das
konkrete normalisierte Ziel gebunden. Der Test muss den tatsächlichen ersten Netzwerk- oder lokalen
Modellaufruf beobachten; ein vorhandener Textschlüssel allein ist kein
Nachweis.
