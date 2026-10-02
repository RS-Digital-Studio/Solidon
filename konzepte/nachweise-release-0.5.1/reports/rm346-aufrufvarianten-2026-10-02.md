# RM346 — Vorwärtskorrektur der sechs konkreten Reviewbefunde

Stand 02.10.2026: Die laufende RM346-Einheit ist korrigiert und unabhängig
zur selektiven Integration freigegeben. Kein neuer RM-Punkt wurde begonnen.
Zentrales Tor, Git-Integration und tatsächliche Codex-Clientfreigabe dieser
Einheit werden hier nicht als durchgeführt ausgegeben.

## Historischer Stand und sechs Ursachen

Der erste gehaltene Hookstand `f28f6a42…` bestand seine damaligen 98 eigenen
Fälle und das damalige reine Hookmodul mit 241 Fällen. Der unabhängige Review
fand trotzdem sechs konkrete Lücken. Diese Ergebnisse bleiben historische
Belege ihres jeweiligen Prüfumfangs; sie sind keine Freigabe der neuen Quelle.

1. Ein echtes Semikolon unmittelbar vor `# Kommentar` wurde nicht als Trenner
   erkannt: CPython `shlex` liest den Kommentar samt Zeilenende im c-Zustand
   mit. Der Rohabschnitt war deshalb länger als der Tokenwert.
2. Benannte Start-Process-Werte und Schalter verschoben rohe Tokenpositionen.
   Freie FilePath-/ArgumentList-Werte wurden dadurch übersehen.
3. Die POSIX-Zerlegung nativer Windows-Argumente behandelte einen Apostroph als
   Quotesyntax und verwarf einen gültigen Skriptstart.
4. Die beiden Claude-Bash-Vorfiltergruppen ließen Großschreibung nicht zum
   Python-Hook durch. Dieser engste Konfigurationsbereich samt bestehendem
   Anschlusswächter wurde nachträglich ausdrücklich zentral zugeordnet.
5. Globale Kommatrennung beschädigte bisher gültige native Pfade wie
   `python F:/alt,neu/tools/upload_website.py --help`.
6. Ein Zeilenumbruch in einem gewöhnlichen `@(...)`-Array erzeugte einen
   vermeintlichen zweiten Shellbefehl. Insbesondere konnte eine bloße
   Notepad-Argumentnennung als Werkzeugstart erscheinen.

## Chirurgische Umsetzung

Die vorhandene Lexerfolge bleibt erhalten. Sie erkennt echte Trenner am
Rohpräfix, berücksichtigt vorher mitgelesene Kommentarzeilen und erhält
zitierte beziehungsweise escaped Trenner als Daten. Kommas bleiben im nativen
Wort; nur am erkannten Start-Process-Kopf werden sie Cmdlettrenner. Die Tiefe
eines solchen literal behandelten Arrays bindet dessen Zeilenumbrüche.
Nach einem echten äußeren Befehlstrenner gilt wieder der native Wortkontext.

Start-Process sammelt benannte Werte getrennt von freien Positionen.
Andere Parameterwerte werden nicht zu Programmnamen; bekannte Schalter
verbrauchen keinen Positionswert. Nur ungebundene FilePath-/ArgumentList-Felder
werden anschließend aus freien Werten belegt. Native Argumente gelangen direkt
zum bisherigen Aufrufparser. Der begrenzte `_windows_arguments`-Helfer verwendet
Microsofts Regeln für `argv[1:]`: doppelte Quotes, gerade/ungerade Backslashes
vor Quotes, leere Werte und das letzte unvollständig geschlossene Quote.
Ein Apostroph ist gewöhnlicher Inhalt. Der Programmname wird separat behandelt.
Windows-Pfadnormalisierung erfolgt erst am tatsächlich geprüften Wort, damit
die nativen Backslash-/Quote-Regeln ihre Daten erhalten.

Der einzige Konfigurationshunk ergänzt `shopt -s nocasematch` vor den beiden
bestehenden PreToolUse-`case`-Gruppen. Trigger, Muster, Approval-/Markerwerte,
ursprüngliche JSON-Nutzlast und deren Weitergabe bleiben bytegleich erhalten.
Der vorhandene Vorfilterwächter berücksichtigt die tatsächlich davor gesetzte
Shelloption und prüft zusätzlich Großschreibung aller sechs Namen aus
`RUECKFRAGE_WERKZEUGE`. Die generierte `.codex/hooks.json` ist unverändert.
Es entsteht keine neue Werkzeugliste oder Abhängigkeit.

## Primärsemantik

Start-Process bindet FilePath an Position 0 und ArgumentList an Position 1;
ArgumentList-Zeichenketten werden mit Leerzeichen verbunden.
[Microsoft Start-Process](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.management/start-process?view=powershell-7.5).
Kommas gehören bei nativen Anwendungen zum Argument; Cmdletarrays haben einen
eigenen Kontext und erlauben Zeilenumbrüche nach Komma oder öffnender Klammer.
[Microsoft about_Parsing](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_parsing?view=powershell-7.5).
Die Quote-/Backslash-Regeln des neuen begrenzten Argumenthelfers entsprechen
der dokumentierten C-Startargumentbildung.
[Microsoft C-Argumentregeln](https://learn.microsoft.com/en-us/cpp/c-language/parsing-c-command-line-arguments?view=msvc-170).
`nocasematch` wirkt auf die Alphabetgroßschreibung in `case`-Mustern.
[GNU Bash, Conditional Constructs](https://www.gnu.org/software/bash/manual/html_node/Conditional-Constructs.html).

Kein Primärquelltext, C-Beispiel oder darin genanntes Programm wurde ausgeführt.
Die tatsächliche Standardbibliotheks-Lexerimplementierung wurde in der lokalen
CPython-3.14.7-Laufzeit gezielt gelesen.

## Tatsächliche kleine Entwicklungsbelege

| Lauf | Testkörper | Rot | Grün | Errors / Skips | Exit |
|---|---:|---:|---:|---:|---:|
| Gehaltene f28-Quelle und unveränderter Vorfilter (`before`) | 63 | 44 | 19 | 0 / 0 | 1 |
| Parser korrigiert, Vorfilter noch unverändert (`after-v1`) | 63 | 1 | 62 | 0 / 0 | 1 |
| Vorfilter eng korrigiert (`after-v2`) | 63 | 0 | 63 | 0 / 0 | 0 |
| Endgültige Quelle und eigener statisch korrigierter Teststand (`after-final`) | 63 | 0 | 63 | 0 / 0 | 0 |
| Ursprüngliche 98 eigenen Fälle am endgültigen Stand (`original-98-final`) | 98 | 0 | 98 | 0 / 0 | 0 |

Die neue Auswahl enthält 39 Ausgangsfälle (13 Formen × ask/deny/Freigabe),
15 Negativformen, sieben tatsächliche native Kindparser-Anschlüsse und beide
Fälle des vorhandenen Vorfilterwächters. Positiv- und Negativformen iterieren
über alle sechs Namen aus der Quelle; Negativformen prüfen beide Clientausgänge.
Diese Schleifen sind keine zusätzlichen JUnit-Testkörper. Die Kindargumentfälle
beobachten `_werkzeug_aufruf` und delegieren jeden Aufruf unverändert an dessen
echte Umsetzung. Es wird kein Erkennungsergebnis vorgegeben.

Gemockt werden weiterhin nur Payload/Clientkennung am echten `vor_bash`-Einstieg.
Keine geschützten Geld-, Upload-, Signier- oder Veröffentlichungswerkzeuge,
keine Clientaktionen und keine neuen echten Kern-/Fensterprozesse wurden gestartet.
Der Vorfilteranschluss ist am gespeicherten Bash-Befehl und dessen Mustern geprüft,
keine ausgeführte Claude-/Codex-Clientabnahme.

Je Lauf sind fünf Quell-/Test-/Konfigurationshashes vor/nach identisch.
Rohtext, JUnit, nativer Exit und Auswahl bleiben pro Phase getrennt erhalten.
`proof-audit.json` gleicht tatsächliche JUnit-Testkörper und Fehlertypen gegen
Resultate und Exits ab. Der einzige Zwischenfehler benennt den bestehenden
PreToolUse-Vorfilterwächter und tatsächlich alle sechs versteckten Großschreibungen.
Die ersten eigenen Ruff-/Formatbefunde sind als statische Befunde erhalten;
chirurgisch korrigierte Endstände haben jeweils Exit 0. Keine ganze Datei wurde
automatisch umformatiert.

## Selektiver Übergabestand und Grenzen

| Datei | Endgültiger SHA256 |
|---|---|
| `.claude/hooks/solidon3d_hooks.py` | `a0be36cbdbdc5777f7e8010e0226022b2bc91dcd82084ef9bc224979f36ab8ef` |
| `tests/test_solidon3d_hooks.py` | `dd46e79e09978c4241c0ab5dff04468479eea4a007ef62acab7f753989df2334` |
| `.claude/settings.json` | `50ca7fde6f222c31b13c5a0cceee95d6898f0d96af32abc35421ca2267f41c88` |
| Unveränderte `.codex/hooks.json` | `05d348a6460eb5d2294c2bb5f3523cc43db37386a7708e1edd4e698f334bc84b` |

`own-source-hunks.json`, `own-test-hunks.json` und `own-config-hunks.json`
enthalten die kumulativen exakten Basis-/Kandidatenhunks. Die zusätzlichen
`own-forward-*-hunks.json` zeigen ausschließlich den Nachgang ab f28/4aa/e125.
`source-before/`, `source-after/`, die Diffs und Vorwärtsrekonstruktion sichern
die Änderungsgrenze. Der gesamte Source-Präfix und -Suffix außerhalb der
Werkzeugparser sind exakt erhalten. Alte Testbytes außerhalb des einzelnen
Imports, des eigenen Anhangs und der ausdrücklich zugeordneten Vorfilterhelfer/
Wächter sind erhalten. Der Konfigurationsvergleich erlaubt nur den einen
PreToolUse-Präfix; die generierte Konfiguration ist bytegleich.

Die bisherige Handoffliste und sämtliche historischen f28/98/241-Rohbelege
sind unverändert erhalten und ihre Identitäten im neuen Audit aufgeführt.
Ein vollständiger neuer Hookmodullauf wurde während des zentralen Tors nicht
ausgeführt; 241 grüne Fälle werden ausdrücklich nur dem früheren Stand
zugeordnet. Der erneute unabhängige Review ist mit JA abgeschlossen;
zentrales Tor und selektiver Commit/Push bleiben Integrationsschritte. `/hooks` im tatsächlichen
Codex-Client bleibt unbestätigt. Fenster, Renderer, Leistung, Paket und Release
sind keine Abnahme dieser Entwicklungsgruppe.

## Abschließender unabhängiger Review und tatsächlicher Anschluss

`/root/rm298_lifecycle_review` hat den vollständigen eigenen kumulativen
Diff und seine vorwärts gerichteten Gegenstücke gelesen: **JA für neun
Quell-, neun Test- und einen Konfigurationshunk; alle sechs F28-Befunde
behoben, kein weiterer blockierender Fund im eigenen geprüften Umfang**.
`FINAL_REVIEW.md` hat SHA256
`34cc8b989964caf3b8cea63db38184ed50f527011e50472d08884d3081c7aa7c`.

Die kumulative Basis ist die ursprüngliche Quelle
`ef86d8d58a5c9deff966c7f7d27cf614dd16b3fab6afa6e7730097c3b3226c38`;
die frühere f28-Fassung ist nur die Basis des nachfolgenden Reviewfixes.
Beide Hunkfolgen rekonstruieren den jetzt gehaltenen a0be-Kandidaten
bytegenau. Historische Diagnose-, Lauf- und NEIN-Berichte bleiben erhalten.

Der Review gleicht alle fünf neuen Phasen aus Rohtext, JUnit, nativen
Ausgängen und fünf stabilen Quell-/Test-/Konfigurationshashes ab. Die
finalen 63 und die ursprünglichen 98 sind tatsächlich am finalen Stand
grün; die vollständigen 241 gehören ausdrücklich zur früheren f28-Quelle.
Der lesende Beleg erzeugt keinen neuen Lauf und keine Clientfreigabe.

Die Quelle und Konfiguration sind an ihren gespeicherten tatsächlichen
Hookeinstiegen geprüft. `settings.json` behält Freigabe-/Marker-/Triggerwerte;
die generierte `.codex/hooks.json` bleibt bytegleich. Für eine bestätigte
Codex-Anwendung ist zusätzlich die in `CLAUDE.md` vorgeschriebene
erneuerte `/hooks`-Freigabe im tatsächlichen Client erforderlich. Diese
Abnahme ist hier unbestätigt; gespeicherte Konfiguration und reine Tests
werden nicht als Ausführung in Claude oder Codex ausgegeben.

Örtliche Originale liegen in
`tmp/review-seit-0.5.1-2026-10-01/rm346-aufrufvarianten-20261002-7db5/forward-review/`.
Der portable Bericht hält die Ursachen, Semantik, Zahlen, Quellidentitäten
und Abnahmegrenzen auch ohne diesen ignorierten Laufordner fest.

## Nachtrag: gebundene PowerShell-Parameter

Der zentrale Nachreview belegte einen weiteren übersehenen Start:
`Start-Process -FilePath python -ArgumentList:tools/check_support.py`.
Die allein gebundene `-FilePath:python`-Form war bereits grün und bleibt
Kontrolle; sie ist kein zweiter belegter Schutzverlust.
Der Binder trennt unzitierte Parameternamen am ersten Doppelpunkt und
reicht den gebundenen Wert mit seinen Literaleigenschaften weiter.
Weitere Doppelpunkte und zitierte Trenner bleiben Daten.

Die unmittelbare Negativkontrolle mit zitiertem
`'-ArgumentList:tools/run_agent_suite.py'` machte danach eine weitere
enge Anschlusskorrektur nötig: Der Python-Kindparser beendet unbekannte
Optionsargumente nach seinen bestehenden Options- und Modulregeln,
statt deren letztes Pfadsegment als Skript zu erkennen.

| Tatsächlicher Lauf | Körper | Rot | Grün | Errors / Skips | Exit |
|---|---:|---:|---:|---:|---:|
| Neue Fälle vor dem Binderfix | 65 | 44 | 21 | 0 / 0 | 1 |
| Binder korrigiert, Negativkontrolle noch rot | 65 | 1 | 64 | 0 / 0 | 1 |
| Endgültiger Binder und Kindparser | 65 | 0 | 65 | 0 / 0 | 0 |
| Vorherige Reviewgruppe am neuen Stand | 63 | 0 | 63 | 0 / 0 | 0 |
| Ursprüngliche eigene Gruppe am neuen Stand | 98 | 0 | 98 | 0 / 0 | 0 |

Die 44 Vorherfehler sind 39 Binder- und fünf Literalübergabe-Assertions.
Die ausschließlich gebundene FilePath-Form und vollständig getrennte
Werte bleiben jeweils drei grüne Kontrollen. Alle Laufphasen sichern
fünf identische Vorher-/Nachherhashes. Ruff und drei eigene Formatbereiche
sind grün; es gab keinen weiteren Vollmodullauf.

| Finaler Prüfling dieses Nachtrags | SHA256 |
|---|---|
| `.claude/hooks/solidon3d_hooks.py` | `e29131e33103d50b115cbdced8e6b8ad20abe6ce2bfb746e894a5eaf73acf206` |
| `tests/test_solidon3d_hooks.py` | `db58977194ad4de8a0d24c6d86195344b36e4b412820479cd03b420ca6928ff8` |

Die Konfiguration bleibt am oben belegten Stand. Die kumulative Übergabe
enthält jetzt zehn Quell-, neun Test- und den unveränderten einzelnen
Konfigurationshunk. Der neue Vorwärtsschritt umfasst drei Quell- und
einen Testhunk; ältere Testbytes und Belege bleiben erhalten.
Originale und unabhängiger Nachreview liegen im benachbarten
`bound-parameters/`. Zentrales Tor, Integration und tatsächliche
Clientfreigabe bleiben getrennte Nachweise.

## Nachlauf des bestehenden Schreibvorfilters

Das zentrale Schlussgate fand noch einen Testanschluss: Der vorhandene
PostToolUse-Wächter entpackte die um den Großschreibungsmodus erweiterte
Rückgabe von `_claude_filter` nicht. Der einzelne Test wurde vor dem Fix
mit `TypeError` reproduziert. Drei geänderte Zeilen entpacken beide Werte
und berücksichtigen den Modus; Nichtleerprüfung, Python- und Speicherpfad
sowie die negative Markdownkontrolle bleiben erhalten.

Danach bestanden tatsächlich **alle 367 Fälle der Hook-Testdatei**, Exit 0,
keine Errors oder Skips, vier Prüflingshashes während des Laufs unverändert.
Ruff und vollständige Formatprüfung der Datei: Exit 0. Hookquelle und beide
Konfigurationen wurden dafür nicht geändert. Der frühere rote Gesamtlauf
bleibt ein eigener Befund; das gemeinsame Entwicklungstor ist erneut nötig.
Örtliche Originale: `gate-write-prefilter/` neben `bound-parameters/`.
