---
name: bekannte-familie-erklaert-nicht-den-ausloeser
description: "Wer einen Absturz einer bekannten Fehlerfamilie zuordnet, hat den Mechanismus erklärt und den Auslöser übersprungen — bei „seit Commit X" ist die Gegenprobe auf dem Stand davor zwei Minuten wert."
metadata:
  type: feedback
---

Eine bekannte Fehlerfamilie (hier: die VTK/Qt-Absturzfamilie mit eigenem
Registerpunkt) ist die **bequeme** Erklärung. Sie stimmt oft — und liefert die
Freisprechung des eigenen Commits gleich mit, ohne dass jemand sie geprüft hat.
**Familie = Mechanismus. Auslöser = eine andere Frage.**

Am 26.08.2026 zweimal an einem Tag, in beide Richtungen:

- 1a schrieb mir einen Riss in `test_analysis_ui.py` zu; die Gegenprobe
  widerlegte es (meine Hunks lagen woanders, 3/3 grün solo).
- d1 meldete umgekehrt „`test_print_settings_ui.py` reißt **seit deinem
  Plattenwahl-Commit**" — und ordnete es derselben Familie zu, „kein Verdacht
  gegen deinen Commit". Gemessen: Stand davor 73 passed, Exit 0; danach
  reproduzierbar Zugriffsverletzung. Es *waren* meine zwei Tests.

**Why:** Wer „seit Commit X" schreibt, hat die Korrelation schon gesehen und
sie dann weginterpretiert. Genau dort ist der Beleg am billigsten und wird am
seltensten geholt. Und eine falsche Zuschreibung im Register hält Jahre.

**How to apply:** Bei „seit Commit X" **immer** die Gegenprobe auf dem Stand
davor — Arbeitsbaum, ein Lauf, zwei Minuten:

    git worktree add -q --detach "$TEMP/vorher" <commit>^
    cd "$TEMP/vorher" && <voller-pfad>/python.exe -m pytest <datei> -q -p no:randomly

Bei Fensterdateien `-p no:randomly` setzen, sonst misst man die zufällige
Reihenfolge. Und die Zuordnung dann in zwei Sätze trennen: Was ist der
Mechanismus, was war der Auslöser? Beim Fall oben stimmte die Familie und die
Freisprechung trotzdem nicht — der Auslöser war die **Zusammensetzung** der
Datei, nicht der Inhalt eines Tests: ein trivialer Zusatztest an derselben
Stelle war folgenlos, Zusammenlegen zu einem Test verschob den Absturz nur um
eine Position. **Das Muster ist allgemeiner als Abstürze.** Am selben Tag ein dritter
Fall, anderes Gebiet: 27 sah in ihrem Commit 60 Einfügungen statt der
eigenen 45 und schrieb den Rest dem Formatter-Hook zu, der kurz vorher
gelaufen war — tatsächlich hatte ihr `-o`-Commit meine Zeilen
mitgenommen. Ihre eigene Kontrolle prüfte „genau eine Datei im Index"
und war für fremde Zeilen *in* dieser Datei blind.

Die Gemeinsamkeit aller drei: **Eine plausible Erklärung, die zufällig
entlastet, wird nicht geprüft.** Die bekannte Fehlerfamilie, der
Formatter-Hook, der Abriss-beim-Abbau — jede stimmt in vielen Fällen,
und genau deshalb hört das Nachdenken dort auf. Der Prüfreflex gehört
an die Stelle, an der eine Erklärung **einen selbst freispricht**.

Verwandt mit [[messwerkzeug-misst-sich-selbst]],
[[leistungstests-fremdlast]] und [[commit-o-nimmt-den-dateistand]].
