# Fester Remote-Quellenreview 6e1c489 → 6c9420b1f

Basis `6e1c4896fc77cf972260068f0635816f39c96238`, Ziel `6c9420b1fc78da491a9d7eff89279648b1b68d9e`. Alle genannten Zeilen gehören zum gesicherten Zielstand, nicht zum beweglichen Hauptbaum.

**Urteil: Nein. Vier neue P2 im zugeordneten UI-Anschluss.** Sämtliche Diffzeilen der zwölf Prüflingpfade gelesen (+939/−13). Keine Tests, Produktimporte, Fenster- oder Leistungsläufe.

## R6C942-01 — P2: Export nach Abbruch wartet ohne laufenden Auftrag

**Stelle:** `app/ui/main_window.py:7829`.

Vorhandenes Modell ändern, laufende Auswertung abbrechen, danach Exportieren und Dateiziel bestätigen:

- `Session.evaluate_async:4441` setzt `result_current=False`; `cancel_evaluation:4647–4649` beendet den Lauf und verwirft den Nachlauf.
- `session.py:5622–5636` und `5698–5732` melden nur Abbruch/idle; `current` bleibt falsch. `main_window.py:4987` lässt Export bei vorhandenem altem Ergebnis zu.
- `main_window.py:7829–7850` reiht auch `busy=False/current=False` ein, startet aber keine Berechnung. `set_export_choice:2909–2928` ändert nur Exportangaben und meldet `projectChanged`.
- Die automatischen Fortsetzungen `_on_scene:19772` und `_on_busy(False):20535` benötigen einen späteren neuen Lauf; `_export_when_current:7951–7953` lehnt `current=False` erneut ab.

Es entsteht keine Datei, und es läuft keine Rechnung. Die Fortschrittsanzeige behauptet dennoch eine laufende Berechnung. Erst eine weitere Dokumentänderung oder Abbrechen des Exportwunsches löst den Zustand.

**Korrektur:** Aktiv rechnenden und idle-veralteten Stand unterscheiden; im zweiten Fall einen aktuellen Lauf starten oder mit verständlichem Wiederanlaufweg ablehnen. Auch Auswertungsfehler/Abbruch müssen einen wartenden Auftrag eindeutig abschließen. Vertrag: §2.7, §2.8, §29.

**Gegenfall:** Nach tatsächlich abgebrochener Auswertung darf Export weder alte Geometrie schreiben noch ohne Arbeiter warten. Auswertungsfehler während eines wartenden Exports ebenfalls berücksichtigen.

## R6C942-02 — P2: Erhaltenes altes Bild verliert Ansichtsfilter

**Stelle:** `app/ui/main_window.py:19916` im Anschluss an `19852–19854` und `19887–19891`.

Zwei Körper, einen ausblenden bzw. eine einzelne Platte betrachten; danach Halt am ersten Schritt ohne Ergebnisobjekte, etwa durch eine beschädigte/ältere Parameterbelegung:

- `_show_scene:19852–19854` schneidet `_hidden` mit den leeren aktuellen `result.scene.objects` und ruft `viewport.set_hidden(empty)` auf.
- `Viewport.set_hidden:8078–8089` baut bereits dadurch das bisherige Bild ohne Ausblendungen neu auf.
- `main_window.py:19887–19891` setzt die Plattenanzahl aus dem leeren Halt auf eine Platte. `Header.show_plates:522–574` fällt bei vorheriger höherer Platte auf Alle Platten zurück und meldet den Wechsel.
- Erst `main_window.py:19916` verwendet `_picture_for`, das in `19789–19796` die vollständige alte Szene zurückgibt. Es stellt deren Ansichtsfilter nicht wieder her.

Bewusst ausgeblendete Körper und zuvor weggefilterte Platten erscheinen ungefragt. Der aktuelle leere Objektbaum bietet die alten Körper nicht zum erneuten Ausblenden an.

**Korrektur:** Vor dem Ändern von Ansichtsfiltern bestimmen, welches Bild gezeigt wird; für ein erhaltenes Bild dessen Ausblendungen/Plattenwahl bewahren. Fehlerbericht und Verlauf dürfen weiterhin den aktuellen Halt zeigen. Vertrag: §15.3, §18.8, §25.

**Gegenfall:** Ein am ersten Schritt erzwungener Halt erhält neben der alten Geometrie ausgeblendete Kennungen und die gewählte Platte. Eine spätere echte Körperlöschung räumt die Filter weiterhin auf.

## R6C942-03 — P2: Eingaberest wandert in ein anderes Projekt

**Stelle:** `app/ui/panels.py:3657`, insbesondere `3683–3695`.

Projekt A und B enthalten beide `breite=60, maximum=100` und identische Zeilenmetadaten. In A `150` eingeben und ablehnen lassen, anschließend B öffnen:

- `labels.py:578–583`, `605–613` und `627–638` lassen die abgelehnte 150 im Textfeld stehen; der gespeicherte Spinwert bleibt 60.
- `Session.open_project:1952–1957` ersetzt das Projekt direkt. `_reset_for:2137–2169` meldet den Projektwechsel ohne vorheriges Leeren des Parameterpanels.
- `MainWindow._on_project:20088` und `_refresh_parameters:22001–22004` reichen B an `show_document` weiter.
- `panels.py:3639–3659` vergleicht nur Zeilenmetadaten, keine Dokumentidentität. Bei gleichbleibenden Grenzen und `editor.value()==parameter.value` überspringt `3683–3695` sowohl das Setzen des Textes als auch das Abräumen der Ablehnung.

B zeigt deshalb A's ungespeicherte 150 samt alter Ablehnungszeile, obwohl B den gültigen Wert 60 gespeichert hat. Auch das folgende Berechnungsergebnis beseitigt diesen Zustand nicht.

**Korrektur:** Wiederverwendung innerhalb desselben Dokuments von einem Dokumentwechsel unterscheiden. Bei einem neuen Dokument Eingabe-/Ablehnungszustand neu an dessen Werte binden; innerhalb eines Dokuments Fokus und offene Eingabe erhalten. Vertrag: §2.1, §13 und Dokumentbindung der UI.

**Gegenfall:** Zwei Projektdateien mit identischen Parameterzeilen nacheinander öffnen: B zeigt nur eigene gespeicherte Werte und keine Ablehnung aus A. Wiederholte Pfeiltasten in A behalten weiterhin Widget und Fokus.

## R6C942-04 — P2: Korrektur eines Ausdrucks führt zum falschen Feld

**Stelle:** `app/ui/main_window.py:21709`.

Eine zu korrigierende Projektdatei enthält `create_box.width = "=max(@breite, 2000)"` mit `breite=60`. Im Prüfbericht Eingabe korrigieren wählen:

- `primitive_ops.py:248–254` begrenzt Breite auf 1000 mm. `registry/params.py:453–459` erzeugt den Fehler mit `field=width`; `evaluate.py:694–719/5666–5703` trägt ihn mit der Operationskennung in den Bericht.
- `expressions.references:340–344` meldet für diesen gültigen Ausdruck genau eine Referenz `breite`.
- `main_window.py:21709–21718` leitet allein wegen `len(read)==1` zur Parameterleiste und kehrt vor `edit_operation` zurück.
- `max(breite,2000)` bleibt für jeden Parameterwert mindestens 2000. Die Änderung in der vorgeschlagenen Zeile kann den Fehler nicht beheben. Vor dem Delta öffnete dieser Pfad den Schrittdialog.

Der ausdrücklich angebotene Korrekturweg zeigt auf eine Größe, die den Fehler nicht beseitigen kann, und verbirgt den zu ändernden Ausdruck.

**Korrektur:** Die automatische Umleitung auf unveränderte direkte Bindungen begrenzen oder bei zusammengesetzten Ausdrücken auch den echten Formel-Editor zugänglich lassen. Vertrag: §2.1, §2.7, §13, Regel 17.

**Gegenfall:** Direktes `=@breite` führt weiterhin ins Maß; ein zusammengesetzter Ausdruck mit nicht behebbarer Konstante führt zu seiner korrigierbaren Formel. Der neue Regressionstest deckt nur die direkte Bindung ab.

## Weitere Prüfung und Grenzen

- Die Grenzabfrage verändert keine Dokumentwerte. Grenzen kommen aus dem Register; abgeleitete Maße laufen über den vorhandenen Ausdrucksauswerter, unterdrückte Schritte bleiben ausgenommen. Der Bestandsfehler-Vergleich in `change_parameter`/`edit_parameter` bewahrt den Reparaturweg; History/Undo werden erst nach Annahme verändert.
- Die Vorschau meldet `asked` → `explained` → `done(None)`. Session prüft die Generation, MainWindow zusätzlich Eigentümer, Revision, Dokumentzustand, Ergebnis und Auswahl. Ablösung erzeugt eine neue Freigabe; `questioned` verhindert nur erneutes Sperren desselben Auftrags. Der wartende Klick wird vor seinem Aufruf verbraucht. Kein weiterer bestätigter Befund in diesem Anschluss.
- Beim regulär laufenden Export wartet die Fortsetzung bis zum aktuellen Ergebnis und Ende des zugehörigen Workers. Projektidentität und Schließen werden vor dem Schreiben geprüft; Abbrechen löscht den wartenden Auftrag. Die oben genannten Randfälle fehlen in den neuen Tests.
- Alle acht neuen Schlüssel je Katalog gelesen, fünf Sprachen vollständig; Platzhalter je Schlüssel/Wert stimmen überein (reine JSON-/Textprüfung). Zwei Schlüssel zu kleinster/größter Parameterzahl stammen aus dem separat geprüften Agentenweg; dessen Implementierung ist ausgeschlossen.
- Relevante Karten/Regeln und Bauplan §2.1/2.7/2.8, §13, §15.3–15.7, §18.8, §29 herangezogen. Die 22 harten Regeln auf den Scope angewandt: keine neuen Qt-Kernimporte, Produktdateiformate, Zufallsverfahren, Geometrieänderungen außerhalb Ops oder Abhängigkeiten. Fehler-/Bedienverträge betreffen die vier P2.
- Die Fensterfälle wurden nur gelesen. Das direkte MainWindow im neuen Vorschau-Test wird durch die zentrale Autouse-Abbaufixture erfasst; daraus kein fehlender Teardown-Befund. Behauptete frühere Läufe im Remote-Archiv sind kein selbst geführter Nachweis dieses Reviews.

## Zusammenspiel mit laufenden Einheiten

RM298e ist im festen Remote-Ziel noch nicht enthalten. Seine synchronen Ablöse-/Wartehunks in `Session.evaluate_now` sowie `_ask` sind vom Remote-Diff funktional getrennt. Die neue Exportfortsetzung verwendet weiterhin den vorhandenen `result_current`-/`busy`-/`finished`-Anschluss; der Timeout darf keinen Export des alten Ergebnisses freigeben. Keine neue Ursache im bereits geprüften RM298e-Patch gefunden.

RM341/RM342 betrifft den Druckdialog und die Haftungsauflösung. Die beweglichen Hunks wurden nicht verwendet oder mitselektiert; die beiden zuvor separat gemeldeten P2 bleiben separat. Agentenschicht, exaktes Abschneiden samt Geometrietests, Handbuch und vollständiger Roadmap-Review sind nicht Umfang dieses Berichts.

## Vollständige geprüfte Pfadliste

- `app/core/scene/parameter_usage.py`
- `app/ui/main_window.py`
- `app/ui/panels.py`
- `app/ui/session.py`
- `tests/test_operation_ui.py`
- `tests/test_parameter_usage.py`
- `tests/test_ui.py`
- `app/i18n/locales/en.json`
- `app/i18n/locales/es.json`
- `app/i18n/locales/fr.json`
- `app/i18n/locales/it.json`
- `app/i18n/locales/pt.json`

Gesicherte Quellen: `remote-6c942-oberflaeche-quellen/base`, `target`, `diff`; Basis-/Zielhashes in `manifest.json`, weitere feste Anschlussquellen unter `context`. Strukturierte Ergebnisse: `remote-6c942-oberflaeche.json`.

Nur eigene Reviewartefakte geschrieben. Keine Produkt-, QA-, Hauptindex- oder Git-Ref-Änderung; kein pytest, keine Sammlung, kein Produktimport, kein Qt-/Renderer-/Leistungsfall, kein Ruff/Format/mypy oder Entwicklungstor. Die genannten Gegenfälle sind Prüfvorgaben, keine ausgeführten Tests.

Kann das so rein: **nein**, vier P2 sind offen.
