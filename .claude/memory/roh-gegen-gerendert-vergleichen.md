---
name: roh-gegen-gerendert-vergleichen
description: "Ein Test, der Quelltext in fertigem HTML sucht, prüft die Maskierung mit — und wird rot für etwas, das richtig ist, oder grün für etwas, das falsch ist."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: fd3340f1-dc7c-45b2-a76c-25431a7a9212
  modified: 2026-08-27T11:19:13.585Z
---

`assert punkt[:30] in history_html(...)` sucht rohen Quelltext in gerendertem
HTML. Das prüft zwei Dinge auf einmal: ob der Punkt ankommt (gemeint) und ob
er unterwegs unverändert bleibt (nicht gemeint). Sonderzeichen werden
maskiert — `"` → `&quot;`, `'` → `&#x27;`, `<` → `&lt;` —, und genau das soll
passieren.

**Why:** Am 27.08.2026 fiel der Test des Neuerungen-Fensters über drei Punkte
mit `„PETG Rot"`. Der Befund war echt (öffnendes typografisches, schließendes
gerades Anführungszeichen), aber der Weg dorthin war Zufall: Beim Erweitern
auf alle sechs Sprachen wurde derselbe Test sofort für `l'étagère` rot — und
davon stehen 189 in `fr.md`. Der gerade Apostroph ist dort der Bestand, seine
Maskierung ist korrekt, und der Nachbartest besteht für `<` ausdrücklich
darauf. Der Test hätte also einen richtigen Text verworfen.

Die Kehrseite wiegt schwerer: Solange er nur `de` las, blieben achtzehn
falsche Zeichen in `en.md` über mehrere Fassungen unbemerkt. Ein Test, der
das Falsche misst, ist auch dort still, wo er hätte reden müssen.

**How to apply:** Vor dem Vergleich entmaskieren (`html.unescape`), dann
prüft er die gemeinte Frage. Was dabei als Wächter verlorengeht — hier die
typografische Konsistenz —, bekommt einen **eigenen** Test an der Quelle,
nicht am Rendering; und der wird an einer Mutation gegengeprüft, sonst ist er
nur grün ([[messwerkzeug-misst-sich-selbst]]). Dieselbe Frage lohnt bei jedem
Vergleich über eine Wandlung hinweg: Markdown → HTML, `tr()` → Oberfläche,
Zahl → formatierte Anzeige.
