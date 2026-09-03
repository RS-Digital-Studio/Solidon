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

## Am 03.09.2026 dasselbe, und diesmal waren es keine Zahlen

Drei Sitzungen, ein Tag, dieselbe Bauart — nur ging es nicht um übertragene
Werte, sondern um **Zusicherungen**, deren Geltung weiter reichte als der Ort
ihrer Messung. Alle drei fielen erst beim Ausliefern von 0.3.1 auf:

- **Ein Testkörper der falschen Bauart.** Ein Stopfen wurde an der *konvexen
  Hülle* beschnitten. Beim Testkörper war die Hülle der Körper, also war der
  Test grün; bei einem U-Profil ist die Hülle der volle Kasten, und der
  Überstand liegt darin. Drei Handlungen betroffen, eine 10-mm-Platte wurde
  16,03 mm hoch — und die Behebung galt einen halben Tag als fertig.
- **Eine Plattform, auf der die Umgebung anders ist.** Ein Test verlangte
  `assert not animations_enabled()` mit der Begründung „die Suite läuft
  offscreen". Lokal wahr, auf zwei von drei CI-Plattformen zufällig wahr, auf
  Linux falsch: Die CI fährt dort absichtlich unter Xvfb.
- **Eine Fassung, für die eine Datei erzeugt wurde.** `THIRD-PARTY-NOTICES.md`
  trug „Erzeugt für Solidon3D 0.3.0" nach dem Versionswechsel. Eine Zeile von
  809 204 Zeichen, und nur auf Windows sichtbar, weil der Test sich auf den
  anderen Plattformen absichtlich überspringt.

**Was die drei gemeinsam haben, ist nicht die Nachlässigkeit — es ist die
Bauart:** Jede Messung war sauber, und jede galt für einen Punkt, während die
Zusicherung für einen Raum sprach. Deshalb hilft „nochmal messen" nicht; es
kommt dieselbe Zahl heraus. Was hilft, ist die Frage **wofür genau** eine
Messung gilt: für diesen Körper oder für jede Bauart, für diese Plattform oder
für alle drei, für diese Fassung oder für die nächste auch.

Und ein Nachtrag zur Null aus demselben Tag: **Eine Null beweist nichts ohne
einen Gegenwert.** „0,000 mm³ Überstand" kann heißen „nichts da" oder „nichts
gemessen". Erst dass dieselbe Sonde am selben Körper vorher 76,397 mm³ gemeldet
hatte, machte die Null zur Aussage.

**Dasselbe gibt es in der Zeit statt im Ort**, und es ist am selben Tag
zweimal eingetreten. Eine Sitzung meldete „Tor grün" aus vier Läufen, die zu
vier Zeitpunkten liefen — `mypy` vor dem vorletzten Commit, die Suite nach dem
letzten; auf `origin/main` stand danach ein Fehler, den 4246 grüne Tests nicht
sehen konnten. Und mein eigener Index-Fehler war dieselbe Figur: Die Prüfung
war echt und galt für einen Index, den der Commit nicht benutzte. Wo die Zahl
gilt, ist die eine Frage; **wann** sie galt, die andere.

Verwandt: [[messwerkzeug-misst-sich-selbst]],
[[gemessene-frage-ist-nicht-die-gestellte]],
[[bekannte-familie-erklaert-nicht-den-ausloeser]],
[[vier-torlaeufe-ein-stand]], [[privater-index-fester-name]].
