---
name: ki-hinweis-sperrt-den-ersten-modellaufruf
description: "Ein KI-Hinweis schützt nur an jeder echten Modellgrenze; Zielwechsel sperren erneut, Abbruch ruft kein Backend auf."
metadata:
  node_type: memory
  type: project
  modified: 2026-08-31
---

# Ein Informationstext ist erst an der Sendegrenze ein Schutz

Ein vorhandener Dialog, ein Katalogschlüssel oder ein Merker in den
Einstellungen beweist nicht, dass vor der ersten Modellkommunikation wirklich
etwas gezeigt wurde. Der tragende Punkt liegt unmittelbar vor jedem Aufruf,
der ein Modell rechnen lässt. Das ist nicht nur der Agentenzug: Auch eine
Werkzeugprobe sendet einen echten Auftrag. An dieser Grenze stehen Backend,
tatsächliches Datenziel, Nutzlast und Dialogentscheidung gleichzeitig fest.

Der Vertrag besteht aus fünf Teilen:

- Der Wortlaut wird gegen den wirklichen `build_messages`-Pfad geprüft. Eine
  freundliche Kurzfassung ist falsch, wenn tatsächlich Szenensteckbrief,
  Prüfbericht, begrenzter Chatverlauf, Regeln, Werkzeugschemata oder automatisch
  gerenderte Ansichten mitreisen; zugleich wird präzise benannt, was draußen
  bleibt — Projektdatei und Netzgeometrie.
- Anthropic und Ollama werden gegen das tatsächlich gewählte Backend geprüft.
  Bei Ollama gehören Zielklasse und normalisierte, geheimnisbereinigte
  Zieladresse zum Nachweis: Loopback→entfernt und jeder Hostwechsel sperren
  erneut. Ein unbekannter Weg bleibt zu, bis sein Text vorliegt.
- Die primäre Handlung bleibt aus, bis Titel, allgemeiner Hinweis, der richtige
  Anbieterabschnitt und seine Datenschutzanschlüsse in echter Layoutgeometrie
  erreichbar und für Hilfstechnik benannt sind. Visuelles Scrollen ist keine
  Bedingung: Ein Bildschirmleser darf den Accessibility-Baum lesen, ohne einen
  Scrollbalken zu bewegen. Ein bloß programmgesteuertes `accept()` genügt nicht.
- Zurück, Escape, Fensterschließen sowie Darstellungs- oder Speicherfehler
  führen zur Backend-Auswahl und senden nichts. Ein Fehler ist dabei ebenfalls
  fail-closed; ein Protokolleintrag ersetzt den Schutz nicht.
- Der lokale Nachweis enthält nur Textfassung, Backend-Typ,
  Zielklasse/Zieladresse und UTC-Zeitpunkt. Zurücksetzen lebt in den
  Anwendungseinstellungen, nie im Projekt.
- Das Eingabefeld darf für unmittelbare Rückmeldung schon beim Sendeversuch
  leeren, hält aber bis zur Entscheidung den unbearbeiteten Text. Bei Abbruch
  kommen Leerraum, Zeilenumbrüche und Auswahl vollständig zurück.

Geprüft wird nicht nur der Dialog. Backend-Spione sitzen am `MainWindow`-Weg
und an beiden Aufrufen der Ollama-Werkzeugprobe: vor dem Hinweis null, danach
genau der angeforderte Aufruf an dasselbe Ziel. Layouttests sichern Paint,
`heightForWidth`, abgeschaltetes waagerechtes Rollen, großen Text, Tastatur,
zugängliche Namen und die sichtbaren Knöpfe. Ein QObject-gebundener Timer und
`deleteLater()` in `finally` verhindern Nachläufer und Kinderansammlungen. Die
native Gegenprobe bleibt zusätzlich nötig, weil Offscreen keine reale
Schrift-, Bildschirmleser- oder Fensterplattform belegt.

Datenschutzanschlüsse laden nie vor: Die Solidon-Fassung reist als lokale Datei
mit und öffnet in einem reinen Textleser ohne aktive Links. Externe Anbieterlinks
gibt es nur für den tatsächlich gewählten Cloudanbieter; ihr Text sagt vor dem
Klick, dass der Browser aufgeht und übliche Verbindungsdaten anfallen. Ein
entferntes selbst konfiguriertes Ollama-Ziel bekommt keinen erfundenen
Anbieterlink, sondern den sichtbaren Auftrag, den Betreiber zu prüfen.
