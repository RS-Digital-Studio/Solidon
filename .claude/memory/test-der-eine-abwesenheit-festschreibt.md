---
name: test-der-eine-abwesenheit-festschreibt
description: "Ein Test auf „steht NICHT da\" merkt, wenn die Begründung für das Fehlen wegfällt — und wird dann zu Recht rot."
metadata:
  type: feedback
---

Ein Test, der eine **Abwesenheit** zusichert, ist selten und wertvoll: Er
bewacht nicht ein Verhalten, sondern die **Begründung** dafür, dass es das
Verhalten nicht gibt.

Am 03.09.2026 gebaut und am selben Tag eingelöst. `ingest.very_large` bekam
seine Handlung nicht, weil der Befund keine Objektkennung trug — eine Handlung
ohne Ziel landet auf der zufällig gewählten Auswahl. Der Test hielt das fest:

    assert "ingest.very_large" not in FINDING_ACTIONS, (
        "und der ohne Kennung nicht: dort wäre es eine Handlung ohne Ziel"
    )

Sechs Stunden später reichte eine Nachbarsitzung die Kennung nach, und der Test
wurde rot. **Das ist sein Zweck, nicht sein Versagen** — er hat gemeldet, dass
die Voraussetzung seiner eigenen Zusage weggefallen ist. Ohne ihn wäre der
Befund stumm geblieben: Sein Text nennt den Ausweg beim Namen, und der Knopf
hätte an der Zeile daneben gestanden.

**Why:** Die Alternative wäre gewesen, gar nichts zu schreiben — „wir haben uns
entschieden, ihn wegzulassen" steht dann nur in einer Commit-Meldung, die
niemand liest, wenn sich die Lage ändert. Eine Auslassung ohne Wächter ist von
einem Versehen nicht zu unterscheiden.

**How to apply:** Wo eine Entscheidung lautet „dieses eine bewusst nicht", die
Begründung in die Assert-Meldung schreiben und nicht daneben. Wird der Test
rot, ist die erste Frage nicht „wie mache ich ihn grün", sondern **„gilt die
Begründung noch?"** — und wenn nicht, wird die **Zusage** nachgezogen und nicht
der Wert. Ein Test, der eine überholte Bedingung festschreibt, hält den Tag
fest, an dem er geschrieben wurde.

Verwandt: [[zusicherung-wird-stumpf-ohne-rot-zu-werden]] (dort verliert eine
Zusage still ihre Schärfe, hier meldet sie sich), [[fremde-erklaerung-altert-mit]].
