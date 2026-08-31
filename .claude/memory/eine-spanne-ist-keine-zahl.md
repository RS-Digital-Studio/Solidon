---
name: eine-spanne-ist-keine-zahl
description: "Beim Vereinheitlichen auf eine Skala werden bewegliche Werte an ihrem Ende gemessen — und verlieren dabei genau das, wofür sie da sind."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 60dfe3ed-7cce-4c68-a256-9db7aac288cb
  modified: 2026-08-31T06:27:23.152Z
---

Wer viele gewachsene Werte auf eine Skala zusammenzieht, muss die **beweglichen
zuerst aussortieren**. Ein `clamp(2rem, 5vw, 3.5rem)` ist keine Zahl, sondern
eine Spanne; wer ihn über seine obere Kante (3,5rem) einordnet und durch die
nächste Stufe ersetzt, nimmt ihm die Beweglichkeit und merkt es an der Messung
nicht.

Gemessen am 31.08.2026 in `website/style.css`: 44 Schriftgrößen, 37 von 41
Schritten unter sechs Prozent — echter Wildwuchs, die Zusammenfassung war
richtig. Mein erster Entwurf zog aber auch die elf `clamp()`-Werte ein. Die
Bilanz dazu las sich harmlos: „28 Regeln bleiben, 51 verschieben sich unter
einem Punkt, 9 stärker". Hinter den neun standen vier Überschriften, die um bis
zu **acht Punkte** gewachsen wären und ihre Spanne verloren hätten.

**Why:** Die Messung beantwortet die Frage, die man ihr stellt. „Wie weit
verschiebt sich der Wert?" ist bei einer Spanne die falsche Frage — verglichen
wird eine Kante mit einer Zahl, und der Verlust der Spanne taucht in keiner
Differenz auf. Die Zahl war klein und richtig; der Schaden lag daneben.
Verwandt mit [[gemessene-frage-ist-nicht-die-gestellte]] und
[[fuenf-tests-eine-lage]].

**How to apply:** Vor dem Zusammenziehen die Werte in **fest** und **beweglich**
teilen und nur die festen abbilden — `clamp()`, `min()`, `max()`, `em`,
Prozent und `calc()` bleiben draußen. Die beweglichen einzeln ansehen und
begründet entscheiden. Dasselbe gilt für Werte, die aus einem anderen
Bezugssystem stammen: Das Zeichnungsmaß in einer Abbildung (`11px`) richtet
sich nach seiner Zeichnung, nicht nach dem Fließtext der Seite, und ein
Ausreißer mit Absicht (der Preis auf `3rem`, die nächste Stufe 17 Punkte
tiefer) bekommt eine eigene Stufe, statt die Skala zu verbiegen.
