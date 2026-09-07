---
name: ort-statt-zusage-bei-paralleler-arbeit
description: Abstimmung zwischen Sitzungen über Nachrichten ist zustandslos und altert; ein abfragbarer Ort wie gate_lock.py status tut es nicht
metadata: 
  node_type: memory
  type: feedback
  originSessionId: d0102d69-080c-4ecc-9829-61bb385a310d
  modified: 2026-09-07T08:21:09.353Z
---

Am 04.09.2026 haben in diesem Baum sechs Sitzungen gearbeitet, und **zwei
Torläufe sind an derselben Sache verloren gegangen**: Eine fremde Sitzung
schrieb mitten in eine laufende Messung. Beide Male war die Abstimmung
vorher sauber, ausführlich und höflich — und beide Male nutzlos.

**Warum sie nutzlos war:** „Bitte still, bis ich melde" hat keinen Ort, an dem
man nachsehen kann, ob es noch gilt. solidon-e9 hat aus drei Zeitstempeln und
einer fremden Nachricht richtig geschlossen, dass ich wieder schreibe — und
falsch, dass mein Lauf durch sei; die vierte Zahl (wann er begann) hatte ich
nicht mitgeschickt. solidon-52 hatte die Datei-Abstimmung mit zwei Sitzungen
geführt und dabei die Maschinen-Abstimmung übersehen.

> **Eine Nachricht sagt nur, ob gemessen wurde, als sie geschrieben wurde.
> `gate_lock.py status` sagt, ob jetzt gemessen wird.**

**Wie ich das anwende:** Bei paralleler Arbeit verweise ich auf den **Ort**
statt auf eine Zusage von mir — und frage ihn selbst, vor jeder
Schreiboperation, nicht vor jeder Arbeitseinheit. e9 hat daraus die Fassung
gemacht, die nicht vom Erinnern abhängt:

    until ! gate_lock.py status | grep -q "Prozess"; do sleep 15; done

Dieselbe Form hat am selben Tag ein zweites Mal getragen, in einer anderen
Frage: Eine **Anweisung** Roberts kann eine Sitzung nicht weitergeben, eine
**Regel im Repository** kann jeder selbst nachlesen. Auch dort ist der Ort das
Tragende und die Weitergabe das Brüchige — siehe
[[weitergabe-die-handlung-entscheidet]].

**Und die Kehrseite, weil sie Zeit kostet:** Eine Sperre, die sich hinterher
als unnötig erweist, war nicht falsch. solidon-bd hat auf meine Bitte keinen
Pull gefahren, und am Ende gab es nichts zu holen — richtig war sie trotzdem,
denn auf zwei anderen Maschinen hätte jemand committen können.

**Nachtrag 07.09.2026 — der Ort trägt für „was", nicht für „wer".** In einem
Baum mit vier Sitzungen habe ich `git status` gelesen, drei Dateien als
herrenlos eingeordnet und das so an eine andere Sitzung gemeldet; die hat es
Robert als fremde Arbeit berichtet. Eine Stunde später hat sich die dritte
Sitzung gemeldet: Es waren ihre. Der Baum war nicht falsch, meine
**Zuordnung** war es — und für die gibt es überhaupt keinen abfragbaren Ort,
nur Ansagen, die noch nicht geschrieben wurden.

> **`git status` sagt, was geändert ist. Wer es geändert hat, sagt es nie.**

Daraus zwei Dinge: Zuordnung wird als Zuordnung weitergegeben („nicht in
meiner und nicht in deiner Liste"), nicht als Tatsache („herrenlos"). Und wer
eine fremde Einordnung weitergibt, hängt sie an ihre Quelle, damit der
Empfänger sie nicht als geprüft behandelt — dasselbe in kleiner Münze wie
[[weitergabe-die-handlung-entscheidet]].

**Dieselbe Form, anderer Anlass — und sie steht im eingecheckten Gedächtnis
schon einmal:** [[geteilte-umgebung-fragt-das-schloss]] (06.09.2026) fragt
`gate_lock.py status` vor einem Eingriff in die geteilte `.venv`, weil die
Prozessliste zwischen zwei Fensterdateien eines Torlaufs leer ist und nichts
sagt. Hier geht es um Schreiboperationen während einer fremden Messung. Zwei
Anlässe, ein Satz: Der Ort trägt, die Zusage altert.

Verwandt: [[geprueft-fuehlt-sich-wie-vollstaendig-an]],
[[gefilterte-codeansicht-zeigt-keine-zugehoerigkeit]]
