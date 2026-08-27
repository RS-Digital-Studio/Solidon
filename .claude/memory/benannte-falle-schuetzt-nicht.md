---
name: benannte-falle-schuetzt-nicht
description: "Ein Modul, das eine Falle richtig beschreibt, ist gegen sie nicht immun — der Satz liest sich als Beleg, dass jemand nachgedacht hat, und niemand prüft die Stelle noch einmal."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: d52f0866-6a6b-49d3-a8c5-73c0be546ada
  modified: 2026-08-27T15:38:23.696Z
---

Ein Kommentar, der eine Gefahr korrekt benennt, wirkt wie eine Zusicherung.
Er ist keine. Schlimmer: Er **verhindert** die Prüfung, weil er belegt, dass
jemand nachgedacht hat — und wer nachgedacht hat, wird es doch wohl richtig
gemacht haben.

Vier Fälle am 27.08.2026, alle in Code, der die Sache ausdrücklich erklärte:

- **`discover.py`** beschrieb seit je vollständig, wie man ein Programm
  findet, das als Flatpak läuft — und zählte **die eigene Auslieferung nicht
  mit**. Die Slicer-Übergabe war im Linux-Paket tot, ohne dass etwas abstürzt.
- **`find_program`** sagte im Docstring, eine falsche Auskunft sei teurer als
  keine, und meldete zwanzig Zeilen später einen eingetragenen Host-Pfad als
  verschwunden.
- **`updates.MAX_TEXT_LENGTH`** trug eine Rechnung als Begründung: „Selbst 100
  Punkte à 800 Zeichen bleiben unter den 64 KB." Nachgerechnet sind das 78 KB
  — für *eine* Sprache, während `changes` jede trägt. Die Rechnung bestätigte
  genau die Grenze, um die es ging, und beim Kunden riss sie.
- **`cache.put`** benannte im Kommentar, dass zwei `TypeError`-Ursachen
  gleich aussehen und Gegenteiliges meinen — und ließ sie beisammen. Der
  zweite Fall hat danach noch zweimal Tage gekostet.

**Und der fünfte Fall ist diese Erinnerung selbst.** Am selben Tag hatte ich
in `CLAUDE.md` notiert, dass `ruff format` Python-Blöcke **innerhalb** von
Markdown mitformatiert und ein ausgerichteter Kommentar darin das Tor rot
macht. Die Notiz nebenan (`mypy-prueft-die-laufende-plattform`) bekam einen
als `python` ausgezeichneten Block mit genau so einem Kommentar — und machte
das Tor rot. Gefunden hat es 27, nicht ich; die Datei war Sekunden alt.

Der Satz oben wäre beinahe selbst hineingefallen: Er trug das Muster erst
wörtlich, mit drei Backticks am Zeilenanfang, und das **ist** ein Blockstart.
Ein verbotenes Muster wird umschrieben, nicht zitiert
([[waechter-lesen-kommentare-mit]]).

**Why:** Prosa und Prüfung sind zwei Dinge. Der Satz beschreibt, was gelten
soll; ob es gilt, weiß nur eine Messung. Verwandt mit
[[sollwert-aus-dem-pruefling]] — dort erzeugt der Prüfling die Erwartung, hier
ersetzt die Erklärung sie.

**How to apply:**

- **Eine Zahl im Kommentar wird nachgerechnet**, bevor man sie als Beleg
  nimmt. Sie steht dort, weil jemand sie für richtig hielt, nicht weil sie
  geprüft wurde.
- **Wer eine Falle beschreibt, prüft, ob sein eigenes Modul hineinfällt.**
  Die Beschreibung handelt fast immer von *anderen* — fremden Programmen,
  fremden Dateien, dem Nutzer. Der eigene Fall wird mitgemeint und nie
  mitgezählt.
- **Ein Kommentar, der einen bekannten Mangel benennt, ist eine offene
  Aufgabe**, kein erledigter Punkt. Wenn dort „das sieht gleich aus und meint
  Verschiedenes" steht, gehört die Trennung gebaut — oder der Punkt ins
  Register von `ROADMAP.md`.
- Beim Lesen fremder Begründungen: **Je überzeugender der Satz, desto eher
  die Messung.** Ein Abschnitt, der ausführlich erklärt, warum etwas sicher
  ist, ist ein Kandidat, kein Beleg.
