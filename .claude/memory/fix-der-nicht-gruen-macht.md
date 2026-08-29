---
name: fix-der-nicht-gruen-macht
description: "Ein Lauf, der die vermutete Ursache behebt, macht den Test sofort grün — bleibt er rot, war die Diagnose falsch, nicht die Behebung unvollständig."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 4e2b249b-1d42-4020-bb0e-bdcf350ef625
  modified: 2026-08-29T19:51:39.081Z
---

Ein roter Test, eine plausible Erklärung, ein Lauf dagegen — und der Test
bleibt rot. **Dann ist die Erklärung widerlegt, nicht der Lauf unvollständig.**

Am 29.08.2026 an `test_wording.py`: Der Test meldete fehlende Absätze auf der
französischen und italienischen Handbuchseite. Eine andere Sitzung hatte kurz
zuvor die Kataloge committet, also lag die Erklärung nahe — die Seiten sind
veraltet, `make_manual.py` muss laufen. Der Lauf lief, und **der Test war
weiter rot**. Statt daraus zu schließen, dass die Diagnose falsch war, ging sie
als Befund an die Review-Sitzung, von dort in deren Bericht an Robert und
beinahe in die Commit-Meldung.

Grün wurde der Test erst durch eine Änderung an der eigenen Normalisierung:
Ein entfernter HTML-Tag hinterlässt ein Leerzeichen, und hinter dem Apostroph
der romanischen Sprachen (`L’<strong>édition</strong>`) steht es dann in keiner
Quelle. Es gab keine Drift; der Absatz stand in HEAD **und** im Arbeitsbaum.

**Why:** Eine Erklärung, die zu den Fakten passt, fühlt sich wie ein Befund an.
Der billigste Gegentest kostete eine Sekunde — `git show HEAD:<datei> | grep`
— und wurde nicht gefahren, weil die Geschichte schon stimmig war.

**How to apply:** Nach jedem Behebungsversuch die Frage stellen: *Ist der Test
jetzt grün?* Wenn nein, ist die Diagnose zu verwerfen und nicht nachzubessern.
Und vor jeder Behauptung „X ist veraltet" der direkte Blick in den committeten
Stand, nicht in die Erzählung darüber. Siehe [[gemessene-frage-ist-nicht-die-gestellte]],
[[messwerkzeug-misst-sich-selbst]] und [[probe-worktree-altert]].
