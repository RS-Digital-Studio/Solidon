---
name: zweite-stelle-setzt-dieselbe-sichtbarkeit
description: "Wer eine Sichtbarkeit auch wieder auf True setzt, überschreibt jede andere Stelle, die sie ausgeblendet hat — und der Test sieht es nicht, wenn er nur den Aufbau misst."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: b64195e3-fc99-4999-8bdc-0e4ba2801576
  modified: 2026-09-10T15:14:48.016Z
---

Zwei Stellen entschieden über die Menüleiste: `_show_start_screen` blendete die
Arbeitsmenüs beim Wechsel auf die Startfläche aus, `_hide_dead_menus` blendete
sie beim nächsten `_update_actions` wieder ein — es setzt `setVisible(True)`,
sobald ein einziger Eintrag geht. Die letzte Stelle gewinnt, und das war die,
die nur eine Teilfrage beantwortet.

**Why:** Eine Funktion, die einen Zustand auch wieder *einschaltet*, ist keine
lokale Regel mehr, sondern die Autorität über diesen Zustand — sie muss jede
andere Bedingung kennen, unter der er aus bleiben soll. Der Test dazu
(`test_the_start_screen_shows_only_menus_that_do_something_there`) blieb grün,
weil er das frisch gebaute Fenster maß und `action_new` kein `_update_actions`
ruft; in der laufenden Anwendung tut das jedes Signal. Vergleiche
[[waechter-sieht-nur-das-getane]] und [[zwei-dinge-nur-eines-geprueft]].

**How to apply:** Bei einer Sichtbarkeits- oder Freigabelogik erst suchen, wer
denselben Zustand sonst noch setzt (`grep setVisible`/`setEnabled` auf dieselbe
Liste). Wer nur ausblenden darf, blendet nicht wieder ein — oder steigt aus,
wenn eine gröbere Regel schon entschieden hat. Und im Test nach dem Aufbau
einmal den Auffrischweg fahren (`_update_actions`), sonst misst er einen
Zustand, den der Kunde nie sieht — [[oberflaeche-von-hand-fahren]].
