---
name: messung-traegt-nur-am-ort-ihrer-messung
description: "Eine Zahl, die an einer Stelle gemessen wurde, gilt an der nächsten nicht — auch wenn beide dieselbe Sache zu sein scheinen."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 33442ae8-b3cf-4eef-bce4-cf827af80603
  modified: 2026-08-27T09:05:04.164Z
---

Am 27.08.2026 sind an einem Tag **drei** Befunde gefallen, die alle richtig
klangen. Zwei kamen von Agenten, einer von mir:

- **„Der lokale Chat braucht 76 bis 102 Minuten"** — gerechnet über den
  **vollen** Werkzeugsatz. Der Ollama-Weg fährt den **kompakten**
  (`tool_schemas(compact=True)`), und `PROMPT_TOKENS = 19249` ist dort
  gemessen. 19249 / 7,8 = 41,1 Minuten; die Zahl auf der Seite stimmte.
- **„Die Tabellen brechen auf halber Breite ab, 440 px stehen leer"** — die
  Zahl stimmte, der Schluss nicht. Gemessen an der ersten Spalte gegen ihren
  längsten Eintrag: sie **hat** 464 px und **braucht** 316. Verbreitern hätte
  es schlechter gemacht.
- **„Eine Regel, die `figure` ausbrechen lässt, bringt 40 bis 80 Bildpunkte"**
  — von mir, an der *Startseite* gemessen und auf die *Funktionsseite*
  übertragen. Dort misst die Bühne schon 341 bis 353 px bei 375 px Fenster:
  der Ausbruch bringt 29, und aus 3,3 px Schrift werden 3,6.

**Der dritte ist der lehrreichste, weil die Messung echt war.** Sie galt nur
woanders. Zwei Sitzungen hatten die Zahl schon übernommen, bevor ich sie
nachrechnete — niemand misst eine Zahl nach, die jemand als gemessen
weitergibt.

Daraus:

- **Wer eine Zahl weitergibt, sagt dazu, wo sie gemessen wurde.** „Auf der
  Startseite gemessen" ist eine andere Aussage als „gemessen".
- **Wer eine fremde Zahl übernimmt, misst sie an seinem Ort nach**, wenn eine
  Entscheidung daran hängt. Es kostet Minuten.
- **Ein Befund nennt Beobachtung und Schluss getrennt.** Bei zweien der drei
  stimmte die Beobachtung und nur der Schluss war falsch; wer beides
  zusammenzieht, kann den brauchbaren Teil nicht retten.

Verwandt: [[messwerkzeug-misst-sich-selbst]],
[[gemessene-frage-ist-nicht-die-gestellte]],
[[bekannte-familie-erklaert-nicht-den-ausloeser]].
