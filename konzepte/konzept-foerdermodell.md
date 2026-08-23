# Konzept: Monatliche Förderung in drei Stufen

Stand 23.08.2026. Beauftragt von Robert am selben Tag: ein Konzept für eine
monatliche Finanzierung „nebenbei, für Interessierte" in drei Stufen, bei der
die höchste Stufe auch den Lizenzschlüssel enthält — dazu eine Kontrolle aller
Rechtstexte und eine Recherche zur Rechtsform.

Dieses Dokument beantwortet drei Fragen, und sie hängen zusammen: **Was für ein
Modell** darf es sein, ohne das Kernversprechen der Marke zu brechen (§1–§4),
**welche Rechtsform und welche Pflichten** daraus folgen (§5–§9), und **welche
Rechtstexte** dafür geändert werden müssen — einschließlich der Fehler, die
heute schon darin stehen (§10).

> **Keine Rechts- oder Steuerberatung.** Alles hier ist nach bestem Wissen
> recherchiert und mit Fundstellen belegt, aber die Einordnung eines konkreten
> Geschäftsmodells ist eine Beratungsleistung. Was in §5 bis §9 steht, ist als
> **Vorbereitung eines Steuerberater-Gesprächs** geschrieben, nicht als Ersatz.
> Der Betrag für eine einmalige Erstberatung ist gegen das Risiko klein — und
> §10 nennt einen Punkt, der heute schon abmahnfähig ist.

---

## §1 Der Konflikt, den dieses Konzept lösen muss

Solidon3D verkauft sich seit seiner ersten Website über einen Satz: **kein
Abo.** Das ist keine Formulierung, die man nachträglich weich machen kann. Es
steht an sechs Stellen, und an einer davon ist es ein Angriff auf den
Wettbewerb.

| Stelle | Wortlaut |
|---|---|
| `website/index.html:7` | Meta-Beschreibung: „lokal, ohne Konto, **ohne Abo**" |
| `website/index.html:26` | Open-Graph-Beschreibung: dasselbe |
| `website/index.html:196` | Fließtext im Hauptteil |
| `website/index.html:538` | Überschrift des Preisblocks: „Einmalkauf — **kein Abo**, kein Konto, keine Funktion, die nach zwölf Monaten aufhört zu funktionieren" |
| `website/index.html:574` | Verkaufsgrund 2 von 5: „**Einmal, nicht jeden Monat.** Die KI-Dienste, mit denen 3D heute beworben wird, rechnen im Abo ab — 20 bis 30 $ im Monat […] und nach der Kündigung endet der Zugang. Hier sind es 69 € einmal." |
| `README.md:29` | dasselbe Versprechen |

Dazu die Architektur. **Ein Lizenzschlüssel hat kein Ablaufdatum**, und das ist
kein Versäumnis:

```
app/core/activation/key.py:90    class Licence: major, purchased_on, order, holder
app/core/activation/key.py:160   payload = [FORMAT_VERSION, major, days>>8, days&0xFF] + order + holder
```

`days` ist das **Kaufdatum** seit `EPOCH` (01.01.2026), kein Ablauf. Geprüft
wird gegen `major`, die Hauptversion, und sonst nichts. Einen Widerruf gibt es
nicht, weil es keinen Server gibt, der widerrufen könnte. Die Begründung steht
schwarz auf weiß in `konzepte/konzept-veroeffentlichung-1.0.md:132`:

> „Ein Abo bräuchte eine wiederkehrende Prüfung, und die bräuchte einen Server.
> ‚Kein Konto, keine Cloud' ist kein Marketingsatz, sondern eine
> Architekturentscheidung, die im ganzen Kern durchgezogen ist."

Und der Lizenzvertrag verspricht es dem Käufer ausdrücklich: das Nutzungsrecht
ist **„zeitlich unbegrenzt"** und endet nicht mit einer neuen Hauptversion
(`EULA.md`, Nummer 1).

**Daraus folgt hart:** Ein Modell, bei dem die Software nach einer Kündigung
aufhört zu laufen, ist in Solidon3D **nicht baubar** — nicht ohne Server, nicht
ohne Konto, nicht ohne den zentralen Verkaufstext und den Lizenzvertrag zu
brechen. Wer es trotzdem auf die Seite schriebe, gäbe ein Versprechen ab, das
der Code nicht einlöst.

Das ist keine Absage an den Auftrag. Es ist die Bedingung, unter der er
funktioniert.

---

## §2 Die Entscheidung: fördern statt abonnieren

**Ein Fördermodell verkauft keinen Zugang auf Zeit. Es nimmt Geld für ein
Vorhaben und gibt einen Dank zurück.** Der Unterschied ist nicht sprachlich, er
ist der ganze Punkt:

| | Abo | Förderung |
|---|---|---|
| Wofür wird gezahlt? | Zugang, der endet | Fortschritt des Projekts |
| Was passiert beim Kündigen? | Software hört auf | Software läuft weiter |
| Braucht es einen Server? | ja, für die Prüfung | nein |
| Bricht es „kein Abo"? | ja | nein |
| Bricht es EULA Nr. 1? | ja | nein |

Damit bleibt jeder Satz auf der Website wahr. Die Software wird nie im Abo
verkauft; sie hört nie auf zu funktionieren. Wer fördert, tut es, weil er das
Projekt will — nicht, weil sonst etwas abgeschaltet wird.

**Der Lizenzschlüssel in Stufe 3 ist ein Dank, kein Zugang auf Zeit.** Er wird
einmal ausgegeben und bleibt, wie der eines Käufers — auch wenn die Förderung
endet. Technisch geht es gar nicht anders (§1), und rechtlich ist es die
saubere Variante: Man entzieht nichts, also muss man nichts entziehen dürfen.

> Diese Linie ist unabhängig von mir zweimal erreicht worden: `3d-druck-bd` kam
> in ihrer Analyse des Kaufwegs am 23.08.2026 zum selben Ergebnis, aus derselben
> Codestelle heraus. Das erhöht das Vertrauen in die Schlussfolgerung, ersetzt
> aber die fachliche Prüfung in §5–§9 nicht.

### Was das für die Werbung bedeutet

Der Verkaufsgrund auf `website/index.html:574` („Einmal, nicht jeden Monat")
darf **stehen bleiben** — er ist weiterhin wahr und weiterhin der stärkere
Satz. Die Förderung wird nicht neben den Preisblock gestellt, sondern
**woanders**: ein eigener, ruhiger Abschnitt weiter unten oder eine eigene
Seite. Wer kaufen will, kauft. Wer mehr geben will, findet den Weg.

Das ist auch die Antwort auf die Frage, die ein aufmerksamer Leser sonst
stellt: *„Ihr sagt kein Abo und bietet ein Abo an?"* Die Seite muss den
Unterschied selbst benennen, in einem Satz, an genau der Stelle — sonst wirkt
sie unehrlich, und das kostet mehr, als die Förderung einbringt.

---

## §3 Die drei Stufen

Namen im Ton des Projekts, Beträge als Vorschlag. Alle Beträge sind
**Bruttobeträge** — was der Förderer zahlt, steht dran (§7).

| | Name | Betrag | Was zurückkommt |
|---|---|---|---|
| **1** | **Rückenwind** | **3 € / Monat** | Nennung auf der Förderseite (freiwillig, Name oder Pseudonym). Zugang zur Änderungsliste vor der Veröffentlichung. |
| **2** | **Werkbank** | **7 € / Monat** | Alles aus Stufe 1. Dazu: Vorabversionen, sobald es sie gibt, und ein Kanal, über den Wünsche gelesen werden — mit der ausdrücklichen Einschränkung, dass daraus **kein Anspruch** auf Umsetzung entsteht. |
| **3** | **Schlüssel** | **12 € / Monat** | Alles aus Stufe 2. Dazu **der Lizenzschlüssel für Version 1.x** — einmal ausgegeben, dauerhaft, unabhängig davon, wie lange gefördert wird. |

### Warum diese Beträge

- **3 €** ist die Schwelle, unterhalb derer die Zahlungsgebühr den Beitrag
  auffrisst. Bei rund 5 % plus Transaktionspauschale eines Merchant of Record
  (§8) bleiben von 1 € kaum 50 Cent. Drei Euro ist der niedrigste Betrag, bei
  dem Geben und Ankommen noch in einem sinnvollen Verhältnis stehen.
- **12 €** ist so gewählt, dass ein halbes Jahr Förderung (72 €) den
  Einführungspreis von 69 € übersteigt. Das ist die Rechnung, die ein Förderer
  selbst aufmacht, und sie soll für ihn aufgehen.

### Die Lücke, die dabei entsteht — und warum sie offen bleiben sollte

Wer Stufe 3 einen Monat lang zahlt, kündigt und den Schlüssel behält, hat 12 €
statt 69 € gezahlt. Diese Lücke ist **technisch nicht schließbar** (§1) und
zwei Wege stehen offen:

**Weg A — empfohlen: die Lücke bleibt offen, bewusst.** Der Schlüssel kommt mit
dem ersten Beitrag. Begründung: Ein Fördermodell, das misstrauisch gebaut ist,
verfehlt seinen Zweck. Wer 12 € zahlt, um 57 € zu sparen, hätte mit hoher
Wahrscheinlichkeit gar nicht gekauft — und hat immerhin 12 € gegeben statt
null. Der Schaden ist der entgangene Gewinn bei Leuten, die ohnehin nicht
gekauft hätten; das Risiko ist gedeckelt und klein, solange die Förderung nicht
prominenter beworben wird als der Kauf (§2).

**Weg B — die Lücke wird geschlossen: der Schlüssel kommt, sobald die Summe der
Beiträge den Kaufpreis erreicht** (bei 12 € nach sechs Monaten). Dichter, aber
mit drei Nachteilen: er ist erklärungsbedürftig, er verlangt eine Buchführung
über Fördersummen je Person, und **er rückt gefährlich nahe an ein
Teilzahlungsgeschäft nach § 507 BGB** — mit eigenen Informations- und
Formpflichten. Wenn Weg B, dann gehört genau diese Frage dem Steuerberater
beziehungsweise dem Anwalt vorgelegt.

**Empfehlung: Weg A.** Er ist ehrlicher, einfacher und passt zu einem Modell,
das ausdrücklich „für Interessierte" gedacht ist und nicht als Vertriebskanal.

### Was die Stufen ausdrücklich nicht enthalten dürfen

- **Keine Funktion, die es ohne Förderung nicht gibt.** Sonst ist es doch ein
  Abo, nur anders genannt — und der Kern müsste unterscheiden, wer fördert.
  Das bräuchte einen Server.
- **Keinen Anspruch auf Support** und keine zugesicherte Antwortzeit. Ein
  solcher Anspruch wäre eine Dienstleistung mit allen Folgen; die EULA schließt
  ihn heute für die Demo ausdrücklich aus (Nummer 4a).
- **Keinen Einfluss auf die Entwicklung, der über „wird gelesen" hinausgeht.**
  Wer Mitsprache verkauft, schuldet sie.

---

## §4 Was Stufe 3 technisch bedeutet

Nichts am Code. Das ist die gute Nachricht.

Ein Schlüssel entsteht heute über `tools/make_licence_keys.py` und wird mit dem
privaten Teil des Lizenz-Schlüsselpaars signiert; der öffentliche Teil steht in
`app/core/activation/key.py:72`. Für Stufe 3 wird derselbe Weg benutzt wie für
einen Kauf — der Schlüssel lautet auf den Namen des Förderers und trägt die
Bestellkennung des Zahlungsanbieters.

> **Nicht verwechseln:** Es gibt zwei Schlüsselpaare. Das eine signiert
> **Lizenzen** (`key.py`), das andere die **Versionsdatei** fürs Update
> (`app/core/updates.py`, `RELEASE_PUBLIC_KEY`). Verschiedene Paare,
> verschiedene Zwecke; beide privaten Teile liegen nicht im Repository und
> dürfen es nie.

**Der einzige Punkt, der Aufwand macht, ist die Ausgabe.** Bei einem
Einmalkauf liefert der Zahlungsanbieter einen vorab erzeugten Schlüssel aus.
Bei einer Förderung muss jemand merken, dass ein neuer Förderer Stufe 3
erreicht hat, und ihm einen Schlüssel schicken. Bei „nebenbei" und
überschaubaren Zahlen ist das eine Handarbeit von zwei Minuten im Monat — und
sie ist der Grund, die Stufe 3 nicht zu billig zu machen.

**Die Hauptversion ist der natürliche Wiederholungshebel.** Der Schlüssel
bindet `major`; wer heute fördert, hat alle 1.x. Für ein späteres 2.0 braucht
es einen neuen Schlüssel. Das ist serverlos, es nimmt niemandem etwas weg, und
es ist bereits so gebaut und so kommuniziert (EULA Nummer 5). Wenn eine
wiederkehrende Einnahme über die Förderung hinaus gewünscht ist, liegt sie
dort — nicht in einer Abschaltung.

---

## §5 Rechtsform: Gewerbe, und zwar Einzelunternehmen

### Ist es überhaupt ein Gewerbe? Ja, und das ist eindeutig.

Softwareentwicklung **kann** freiberuflich sein (§ 18 EStG, „ingenieurähnliche
Tätigkeit"), wenn sie qualifiziert, planend und dokumentiert erfolgt und
vergleichbare theoretische Kenntnisse vorliegen. Die alte Faustregel
„Systemsoftware freiberuflich, Anwendungssoftware gewerblich" gilt nicht mehr.

**Aber:** Wer **Standardsoftware-Lizenzen verkauft**, handelt gewerblich —
das ist der Punkt, an dem die Abgrenzung für Solidon3D entschieden ist. Nicht
die Entwicklung ist das Geschäft, sondern der Verkauf eines Produkts an viele.
Eine Förderung mit Gegenleistung ändert daran nichts.

**Folge: Gewerbeanmeldung ist erforderlich.** Beim Gewerbeamt der Stadt
Bamberg, Kosten in der Größenordnung von 20 bis 65 €, mit steuerlicher
Erfassung meist unter 100 €. Das Gewerbeamt meldet automatisch an Finanzamt,
IHK und Berufsgenossenschaft weiter.

### Welche Rechtsform?

| | Einzelunternehmen | UG (haftungsbeschränkt) | GmbH |
|---|---|---|---|
| Stammkapital | keines | 1 € bis 12.500 € | 25.000 € |
| Haftung | **unbeschränkt, auch privat** | auf Gesellschaftsvermögen | auf Gesellschaftsvermögen |
| Gründung | Gewerbeanmeldung | Notar, Handelsregister | Notar, Handelsregister |
| Buchführung | EÜR genügt | Bilanz, Offenlegung | Bilanz, Offenlegung |
| Laufende Kosten | nahe null | Steuerberater faktisch nötig | dito, höher |
| Lohnt ab Gewinn | — | — | grob **80.000–100.000 €/Jahr** |

**Empfehlung: Einzelunternehmen.** Begründung, in dieser Reihenfolge:

1. **Der Aufwand einer Kapitalgesellschaft steht in keinem Verhältnis.** Bei
   „nebenbei" und einem Produkt zu 69 € wird die Schwelle, ab der eine GmbH
   steuerlich günstiger wird, auf absehbare Zeit nicht erreicht. Bis dahin
   kostet sie Notar, Bilanz, Offenlegung und Steuerberater — jedes Jahr.
2. **Das Haftungsargument trägt hier weniger, als es klingt.** Es ist das
   Hauptargument für UG/GmbH, und bei Software mit Schadenspotenzial ist es
   ernst zu nehmen. Aber die EULA begrenzt bereits sauber (Nummer 10 und 11:
   Haftung nur bei Vorsatz, grober Fahrlässigkeit und Verletzung wesentlicher
   Vertragspflichten; ausdrücklicher Ausschluss für tragende Teile,
   Medizinprodukte, Fahrzeugtechnik). Was **nicht** ausschließbar ist —
   Produkthaftung, Körperschäden, Vorsatz — bleibt es auch bei einer GmbH nicht
   vollständig, und dagegen hilft eine **Berufshaftpflicht für IT** besser und
   billiger als eine Rechtsform.
3. **Der Wechsel ist jederzeit möglich.** Ein Einzelunternehmen lässt sich
   später in eine UG oder GmbH einbringen. Der umgekehrte Weg ist teurer.

**Wenn eine Rechtsform gewechselt wird, dann später und aus einem konkreten
Anlass** — erster Angestellter, erster Großkunde mit eigenen Anforderungen,
Gewinn jenseits der 80.000 €.

---

## §6 Steuern

### Umsatzsteuer: die Kleinunternehmerregelung trägt zunächst

Seit 2025 gelten neue Grenzen in § 19 UStG: **25.000 € Vorjahresumsatz und
100.000 € im laufenden Jahr.** Wer darunter bleibt, weist keine Umsatzsteuer
aus und führt keine ab. Die Umsätze sind seit 2025 **steuerbefreit** (vorher:
steuerbar, aber nicht erhoben) — ein Unterschied, der bei
grenzüberschreitenden Leistungen zählt. Wird die 100.000-€-Grenze im laufenden
Jahr gerissen, endet die Regelung **ab diesem Umsatz**; das Vorherige bleibt
befreit.

Bei einer Förderung mit drei Stufen und „nebenbei" ist die 25.000-€-Grenze auf
absehbare Zeit die relevante. Zur Einordnung: 25.000 € entsprechen rund
**170 Förderern in Stufe 3 über zwölf Monate** — zusätzlich zu allen Verkäufen,
denn beides zählt zusammen.

### Ist die Förderung überhaupt umsatzsteuerbar? Ja, sicherheitshalber immer annehmen.

Die entscheidende Unterscheidung ist **echter gegen unechten Zuschuss**: Ohne
Gegenleistung liegt kein Leistungsaustausch vor und keine Umsatzsteuer an; mit
Gegenleistung schon.

- **Stufe 3 ist eindeutig ein Leistungsaustausch.** Der Lizenzschlüssel ist
  eine konkrete Gegenleistung. Umsatzsteuerbar.
- **Stufe 1 und 2 sind Grenzfälle.** Nennung auf einer Website und Vorabzugang
  sind Gegenleistungen, wenn auch geringe. Die Finanzverwaltung neigt bei
  Crowdfunding mit Gegenleistung („Crowdsponsoring") zur Steuerbarkeit.

**Praktische Empfehlung: alle drei Stufen als steuerbare Umsätze behandeln.**
Das ist die sichere Seite, es ändert unter der Kleinunternehmerregelung ohnehin
nichts an der Zahllast, und es erspart eine Diskussion bei einer Prüfung. Wer
echte Spenden ohne jede Gegenleistung will, muss sie **getrennt** und ohne
Stufen anbieten — dann aber ohne Nennung, ohne Vorabzugang, ohne alles.

### Einkommensteuer und Gewerbesteuer

- **Einkommensteuer:** Der Gewinn (Einnahmen minus Ausgaben, EÜR) wird zum
  übrigen Einkommen addiert. Bei nebenberuflicher Tätigkeit neben einem
  Angestelltenverhältnis heißt das: Er wird mit dem persönlichen Grenzsteuersatz
  belastet.
- **Gewerbesteuer:** Freibetrag **24.500 € Gewinn im Jahr** für
  Einzelunternehmen und Personengesellschaften. Darunter fällt keine an. Und
  sie wird bei Einzelunternehmen weitgehend auf die Einkommensteuer angerechnet.

### Nebenberuflichkeit: der Punkt, der übersehen wird

Wer hauptberuflich angestellt ist und nebenbei selbstständig, zahlt **keine
zusätzlichen Kranken- und Pflegeversicherungsbeiträge** auf den Gewinn — solange
die Krankenkasse die Tätigkeit als **nebenberuflich** einstuft. Kippt diese
Einstufung, wird der Beitrag nach dem gesamten Einkommen bemessen, und das ist
ein spürbarer Sprung.

Indizien für „nebenberuflich": **unter 20 Wochenstunden** und Einkünfte unter
**75 % der monatlichen Bezugsgröße** (2025 rund 2.809 €). Feste Grenzwerte gibt
es nicht — die Kasse entscheidet im Einzelfall.

**Zwei Dinge, die daraus konkret folgen:**

1. **Die Krankenkasse fragen, bevor die Förderung startet.** Schriftlich, mit
   der erwarteten Größenordnung. Eine Auskunft vorher ist billiger als eine
   Nachforderung hinterher.
2. **Den Arbeitgeber informieren**, falls ein Angestelltenverhältnis besteht.
   Enthält der Arbeitsvertrag eine Nebentätigkeitsklausel, ist die Zustimmung
   einzuholen; ein Verstoß hat arbeitsrechtliche Folgen.

---

## §7 Eigenes Geldkonto

**Gesetzliche Pflicht: nein** — die besteht nur für Kapitalgesellschaften
(GmbH, UG, AG). Einzelunternehmer, Freiberufler und Kleinunternehmer dürfen
grundsätzlich ein Privatkonto nutzen.

**Praktisch: ja, unbedingt.** Drei Gründe:

1. **Die AGB der meisten Banken untersagen die geschäftliche Nutzung eines
   Privatkontos.** Im schlimmsten Fall verlangt die Bank die Umstellung — oder
   kündigt das Konto.
2. **Bei einer Betriebsprüfung wird sonst das gesamte Privatkonto zum
   Prüfungsgegenstand.** Wer geschäftliche und private Zahlungen mischt, legt
   im Zweifel alles offen.
3. **Bei zwölf Zahlungseingängen im Jahr je Förderer** ist eine getrennte
   Buchführung ohne getrenntes Konto Handarbeit, die niemand freiwillig macht.

**Empfehlung:** Ein Geschäftskonto vor dem ersten Fördereingang eröffnen. Es
muss kein teures sein — für ein Einzelunternehmen mit wenigen Buchungen gibt es
Angebote im einstelligen Monatsbereich, und bei manchen Direktbanken kostenlos.
Das ist die billigste der hier genannten Maßnahmen und die mit dem besten
Verhältnis von Aufwand zu ersparter Mühe.

---

## §8 Zahlungsabwicklung

**Empfehlung: Paddle behalten, jetzt aber im Abo-Modus (Subscriptions).**

Die Begründung steht bereits in `konzepte/konzept-veroeffentlichung-1.0.md:254`
und **wiegt bei einem monatlichen Modell schwerer als beim Einmalkauf**: Ein
Merchant of Record wird rechtlich selbst der Verkäufer. Er schuldet die
Umsatzsteuer im Land des Käufers, meldet sie, stellt die Rechnung und klärt die
Widerrufsfrage im Bestellvorgang. Bei Direktverkauf digitaler Güter an
Verbraucher in der EU läge all das beim Verkäufer — samt OSS-Registrierung.

**Aus einem Vorgang werden bei einer Förderung zwölf im Jahr.** Genau die
Pflicht, die ein MoR abnimmt, vervielfacht sich also. Der Aufpreis von rund
5 % plus Transaktionsgebühr gegenüber etwa 1,5 % bei Stripe ist damit besser
begründet als beim Einmalkauf: Bei 12 € im Monat sind das rund 0,42 € je
Buchung Unterschied — für weggenommene Steuer- und Rechtsarbeit an zwölf
Vorgängen.

Paddle betreibt Subscriptions als Kernprodukt und übernimmt als MoR auch
Rechnungen, Streitfälle und Steuerabführung. **Alternativen** mit demselben
MoR-Modell: FastSpring, Lemon Squeezy (heute Teil von Stripe, weiter als MoR
betrieben). Reine Zahlungsabwickler wie Stripe direkt sind hier die falsche
Wahl, weil sie die Steuerpflicht beim Verkäufer lassen.

**Zwei Punkte, die vor dem Start zu klären sind:**

- **Kann Paddle den Kündigungsbutton nach § 312k BGB einlösen?** (§9). Als MoR
  ist Paddle Vertragspartner des Kunden und damit adressiert; belegen ließ sich
  in der Recherche nur, dass Paddle Kündigungen abwickelt — nicht, ob die
  konkrete deutsche Anforderung erfüllt ist. **Vor dem Start bei Paddle
  schriftlich anfragen.**
- **Die Umsatzsteuer-Identifikationsnummer.** Auch Kleinunternehmer nach § 19
  UStG können und sollten eine beantragen, wenn sie mit Plattformen arbeiten,
  die im Reverse-Charge-Verfahren abrechnen. Paddles Gebühren sind eine
  Leistung aus dem Ausland; die Steuerschuld dafür kann auf den Empfänger
  übergehen, und das ist auch als Kleinunternehmer zu erklären. Beantragung
  beim Bundeszentralamt für Steuern, kostenlos.

---

## §9 Was das Modell rechtlich auslöst

Sobald **Stufe 3 den Schlüssel enthält**, ist die Förderung ein **entgeltliches
Dauerschuldverhältnis mit Verbrauchern, online geschlossen** — und damit gilt
das volle Programm. Das ist der Preis dafür, dass die höchste Stufe eine echte
Gegenleistung hat.

### 1. Kündigungsbutton nach § 312k BGB — Pflicht

Bei entgeltlichen Dauerschuldverhältnissen mit Verbrauchern, die online
geschlossen werden können, ist eine Kündigungsschaltfläche vorgeschrieben.
Anforderungen:

- beschriftet mit **„Verträge hier kündigen"** und die Bestätigungsschaltfläche
  mit **„Jetzt kündigen"** oder einer eindeutig entsprechenden Formulierung,
- **ständig verfügbar, unmittelbar und leicht zugänglich** — der BGH hat 2025
  bestätigt, dass das auch für automatisch endende Abos gilt,
- **ohne Anmeldung** erreichbar.

**Fehlt er, kann der Verbraucher jederzeit fristlos kündigen** — und es ist
abmahnfähig.

### 2. Widerrufsrecht

Vierzehn Tage ab Vertragsschluss. Für digitale Inhalte erlischt es vorzeitig
nach § 356 Abs. 5 BGB, wenn der Verbraucher ausdrücklich zustimmt, seine
Kenntnis des Rechtsverlusts bestätigt und eine Vertragsbestätigung erhält —
**genau das beschreiben `WIDERRUF.md` und `AGB.md` § 6 heute schon korrekt.**

**Aber:** Für ein Dauerschuldverhältnis ist die bestehende Belehrung nicht
geschrieben. Sie kennt nur den Einmalkauf. Bei Widerruf digitaler Inhalte ist
**nie Wertersatz** zu leisten (§ 357 Abs. 3 BGB) — ein Punkt, der bei einer
monatlichen Förderung anders wirkt als bei einem Kauf.

### 3. Preisangaben

Der Monatsbetrag ist als **Gesamtpreis** anzugeben, mit dem Hinweis, ob
Umsatzsteuer enthalten ist. Unter der Kleinunternehmerregelung wird keine
ausgewiesen; die Rechnung stellt ohnehin Paddle als MoR (§8).

### 4. Was ausdrücklich nicht nötig ist

- **Keine Mindestlaufzeit** — und sie wäre auch nicht empfehlenswert. Seit 2022
  darf ein Verbrauchervertrag nach Ablauf der Erstlaufzeit höchstens auf
  unbestimmte Zeit verlängert werden, mit einer Kündigungsfrist von höchstens
  einem Monat. Eine Förderung, die man nicht sofort beenden kann, ist keine.
- **Keine Änderung am Code.** Siehe §4.

---

## §10 Kontrolle der Rechtstexte — die Befunde

Geprüft am 23.08.2026: `EULA.md`, `AGB.md`, `WIDERRUF.md` (die Quellen) sowie
`website/impressum.html` und `website/datenschutz.html` (von Hand gepflegt).

> **Wichtig für jeden, der das repariert:** Drei der fünf Dokumente sind
> **Erzeugnisse**. `tools/make_legal.py:38` erzeugt `eula.html`, `agb.html` und
> `widerruf.html` aus den Markdown-Dateien im Repository-Stamm. Wer das HTML
> von Hand ändert, verliert es beim nächsten Lauf — lautlos, weil das Skript
> überschreibt. `impressum.html` und `datenschutz.html` sind dagegen echte
> Quellen. (Hinweis von `3d-druck-3a`, am Skript nachgeprüft.)

### B1 — Abmahnfähig: Verweis auf eine abgeschaltete EU-Plattform

**`AGB.md` § 10 / `website/agb.html`.** Der Text verweist auf die
OS-Plattform der Europäischen Kommission unter
`https://ec.europa.eu/consumers/odr/`.

**Diese Plattform ist am 20. Juli 2025 eingestellt worden.** Rechtsgrundlage
ist die Verordnung (EU) 2024/3228 vom 19.12.2024, die die ODR-Verordnung
(EU) Nr. 524/2013 vollständig aufhebt. Ein fortbestehender Hinweis auf eine
nicht mehr existierende Plattform kann als **wettbewerbswidrig** eingestuft
werden, weil er Verbraucher täuscht.

**Fix:** Den Verweis samt Link streichen. Der zweite Satz des Abschnitts („Wir
sind nicht bereit und nicht verpflichtet, an Streitbeilegungsverfahren vor
einer Verbraucherschlichtungsstelle teilzunehmen") bleibt richtig und
erforderlich — er beruht auf § 36 VSBG und ist von der Abschaltung nicht
betroffen.

**Dringlichkeit: hoch, unabhängig vom Fördermodell.** Das ist der einzige
Befund dieser Durchsicht, der heute schon ein Risiko darstellt.

### B2 — Innerer Widerspruch: wer ist Vertragspartner?

**`AGB.md` § 1 gegen § 4.**

- § 1: „Anbieter ist RS Digital, Robert Schneider […] — im Folgenden ‚wir'."
- § 3: „Der Vertrag kommt zustande, wenn **wir** die Bestellung annehmen."
- § 4: „Paddle tritt dabei als *Merchant of Record* auf und **wird selbst
  Vertragspartner des Kaufs**."

Beides zusammen kann nicht stimmen. Entweder schließt der Kunde den Kaufvertrag
mit RS Digital oder mit Paddle. Die Datenschutzerklärung entscheidet sich
übrigens klar für Paddle („ist damit für die Bestellung und die Zahlung selbst
Verantwortlicher") — die AGB tun es nicht.

**Fix:** § 2 und § 3 so umschreiben, dass die Rollen getrennt sind: Paddle
schließt den **Kaufvertrag** (und stellt die Rechnung), RS Digital räumt das
**Nutzungsrecht** ein (EULA). Das ist die übliche und saubere Konstruktion bei
einem MoR — sie muss nur dastehen.

### B3 — Darstellungsfehler im Muster-Widerrufsformular

**`website/widerruf.html`, Abschnitt „Muster-Widerrufsformular".** Im Browser
steht dort:

> „Hiermit widerrufe(n) ich/wir (\\<em>) den von mir/uns (\\</em>) abgeschlossenen
> Vertrag über den Kauf der folgenden Waren (\\<em>) / die Erbringung der
> folgenden Dienstleistung (\\</em>)"

Statt der Fußnotenzeichen `(*)` steht dort sichtbarer Markup-Müll — und zwar in
dem **gesetzlich vorgegebenen Mustertext** aus Anlage 2 zu Art. 246a EGBGB.

**Die Quelle ist korrekt.** `WIDERRUF.md:92` schreibt `(\*)`, was in Markdown
das richtige Escaping ist. **Der Fehler liegt im Konverter:**

```
tools/make_legal.py:48   _EMPHASIS = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")
tools/make_legal.py:76   result = _EMPHASIS.sub(r"<em>\1</em>", result)   # macht aus \*…\* ein \<em>…\</em>
tools/make_legal.py:77   result = result.replace(r"\*", "*")              # zu spät — das Paar ist schon weg
```

Der Konverter kennt kein Backslash-Escaping. Zeile 77 räumt die übrig
gebliebenen einzelnen `\*` auf (deshalb ist die Schlusszeile „(*) Unzutreffendes
streichen." korrekt), aber die **Paare** innerhalb einer Zeile hat der
Emphasis-Regex vorher schon zu `<em>` verarbeitet.

**Fix:** Das Escape vor den Emphasis-Regex ziehen — `\*` durch einen
Platzhalter ersetzen (wie es `BREAK` und die Code-Sicherung in Zeile 69 bereits
vormachen) und ihn nach allen Ersetzungen zurückwandeln.

**Betrifft `tools/make_legal.py`** — die Datei gehört derzeit niemandem, ist
aber nicht in meinem Anspruch eingetragen. Vor der Änderung ansagen.

### B4 — Nummerierung: Abschnitt 4a steht vor Abschnitt 4

**`EULA.md` / `website/eula.html`.** Die Reihenfolge lautet: „3. Gewerbliche
Nutzung", „**4a. Demo-Version**", „**4. Testlauf**", „5. Updates".

Inhaltlich ist es begründbar — die Demo ist heute der Regelfall, der Testlauf
kommt erst mit 1.0. Für einen Vertragstext ist es trotzdem ein Formfehler: Ein
Leser, der auf „Nummer 4" verwiesen wird, sucht an der falschen Stelle. Und der
Vertrag verweist selbst mehrfach auf Nummern (§8 der AGB auf „Nummer 11", EULA
Nummer 12 auf „Nummern 6 oder 7").

**Fix, geringstinvasiv:** 4a in **4** umbenennen und den heutigen Abschnitt 4
zu **5**, mit Fortzählung — oder, falls die Verweise das teuer machen, dem
Abschnitt 4a einen Satz voranstellen, der die Reihenfolge erklärt.

### B5 — Impressum: fehlende Angaben

**`website/impressum.html`.** Vorhanden und richtig: § 5 DDG (die aktuelle
Norm, das TMG ist abgelöst), Anschrift, E-Mail, § 18 Abs. 2 MStV.

Was fehlt:

- **Umsatzsteuer-Identifikationsnummer** oder, solange keine besteht, ein
  Hinweis auf die Kleinunternehmerregelung nach § 19 UStG. Sobald eine
  USt-IdNr. beantragt ist (§8 empfiehlt das), ist ihre Angabe nach § 5 Abs. 1
  Nr. 6 DDG **Pflicht**.
- **Rechtsform.** „RS Digital, Robert Schneider" nennt sie nicht. Bei einem
  Einzelunternehmen genügt der vollständige Name — der steht da —, aber die
  Firmierung „RS Digital" lässt offen, was sie ist.
- **Telefonnummer.** Nach EuGH-Rechtsprechung nicht zwingend, wenn ein anderer
  schneller Kontaktweg besteht; die E-Mail-Adresse genügt. Kein Fehler, aber
  ein bekannter Streitpunkt.

**Für das Fördermodell kommt hinzu:** Sobald eine Förderung läuft, gehört der
**Kündigungsweg** ins Impressum oder an eine von dort verlinkte Stelle (§9).

### B6 — Was geprüft wurde und in Ordnung ist

- **`website/datenschutz.html`** ist der beste der fünf Texte. Die Zählung ohne
  Cookie ist sauber begründet (Art. 6 Abs. 1 lit. f DSGVO, § 25 TDDDG korrekt
  verneint), der Auftragsverarbeitungsvertrag mit netcup ist genannt, die
  Drittlandsübermittlung nach UK ist mit dem Angemessenheitsbeschluss nach
  Art. 45 DSGVO richtig behandelt, und die drei Netzverbindungen der Anwendung
  sind vollständig und ehrlich beschrieben.
- **`EULA.md` Nummern 10 und 11** (Haftung) sind fachlich solide aufgebaut:
  Kardinalpflichten, unbeschränkte Haftung bei Vorsatz und grober
  Fahrlässigkeit, Produkthaftungsgesetz, ausdrücklicher Ausschluss für
  sicherheitskritische Anwendungen. Das ist die Grundlage der Empfehlung in §5.
- **`AGB.md` § 7** verweist korrekt auf die §§ 327 ff. BGB samt
  Aktualisierungspflicht für digitale Produkte.
- **Die drei erzeugten Texte tragen alle den Entwurfsvermerk** („Sorgfältiger
  Entwurf, aber keine Rechtsberatung — vor der Veröffentlichung fachlich zu
  prüfen"). Der gehört **vor dem Verkaufsstart weg** — und zwar dadurch, dass
  die Prüfung stattfindet, nicht dadurch, dass der Satz gelöscht wird.

### B7 — Nebenbefund: veraltete Preise im Konzeptgedächtnis

`konzepte/konzept-veroeffentlichung-1.0.md` nennt an fünf Stellen 49 € und
79 €. Die Website nennt seit ihrer letzten Fassung **69 € und 99 €**
(`website/index.html:547`). Das Dokument ist bereits als „überholt"
gekennzeichnet, aber die Preisangaben werden zitiert, als seien sie aktuell —
zuletzt in der MoR-Rechnung in Zeile 266.

**Kein Rechtsfehler**, aber eine Stolperstelle: Wer dort die Gebührenrechnung
nachliest, rechnet mit dem falschen Betrag.

---

## §11 Was zu tun ist

Reihenfolge nach Dringlichkeit, nicht nach Aufwand.

| # | Was | Wo | Wann |
|---|---|---|---|
| 1 | **ODR-Verweis streichen** (B1) | `AGB.md` § 10 | **sofort**, unabhängig vom Fördermodell |
| 2 | **Konverter-Escaping reparieren** (B3) | `tools/make_legal.py:76` | vor dem nächsten Website-Upload |
| 3 | **Vertragspartner-Widerspruch auflösen** (B2) | `AGB.md` §§ 1–4 | vor dem Verkaufsstart |
| 4 | **Impressum ergänzen** (B5) | `website/impressum.html` | mit der Gewerbeanmeldung |
| 5 | **EULA-Nummerierung** (B4) | `EULA.md` | bei der nächsten Fassung |
| 6 | Gewerbe anmelden, Geschäftskonto, USt-IdNr. | Gewerbeamt Bamberg, Bank, BZSt | vor dem ersten Geldeingang |
| 7 | Krankenkasse und ggf. Arbeitgeber schriftlich informieren | — | vor dem ersten Geldeingang |
| 8 | Steuerberater-Erstgespräch mit diesem Dokument | — | vor dem ersten Geldeingang |
| 9 | Paddle: Subscriptions einrichten, Kündigungsbutton klären | Paddle | vor dem Start der Förderung |
| 10 | Förderseite bauen, Kündigungsbutton, Widerrufsbelehrung für Dauerschuldverhältnisse | `website/`, `AGB.md`, `WIDERRUF.md` | vor dem Start der Förderung |

**Punkt 1 bis 5 sind Textarbeit und in einer Sitzung zu erledigen.** Punkt 6 bis
9 sind Roberts Entscheidungen und Behördengänge; sie stehen hier, damit keiner
davon vergessen wird.

---

## §12 Was ausdrücklich nicht gebaut wird

- **Kein Zugang auf Zeit.** Die Software läuft weiter, auch nach einer
  Kündigung. Siehe §1 und §2.
- **Keine Server-Prüfung, kein Konto, keine wiederkehrende Aktivierung.** Das
  bricht die Architektur und den zentralen Verkaufstext.
- **Keine Funktion, die nur Förderern offensteht.** Sonst müsste der Kern
  unterscheiden, wer fördert — und das bräuchte wieder einen Server.
- **Kein Widerruf ausgegebener Schlüssel.** Technisch nicht möglich (§1) und
  als Versprechen unehrlich.

---

## §13 Was Robert entscheiden muss

Alles andere in diesem Dokument ist begründet und ausgearbeitet. Diese fünf
Punkte sind Geschäftsentscheidungen und keine fachlichen:

1. **Weg A oder Weg B** bei der Schlüsselausgabe in Stufe 3 (§3). Empfehlung: A.
2. **Die Beträge** — 3 / 7 / 12 € sind ein begründeter Vorschlag, kein Ergebnis.
3. **Ob die Förderung überhaupt jetzt startet** oder erst nach dem Verkaufsstart
   von 1.0. Dafür spricht: Vor dem Verkauf gibt es keinen Kaufpreis, gegen den
   sich Stufe 3 rechnen ließe, und die Rechtstexte müssen ohnehin zuerst
   fachlich geprüft werden.
4. **Wo die Förderseite steht** — eigener Abschnitt auf der Startseite oder
   eigene Seite. Empfehlung: eigene Seite, verlinkt aus der Fußzeile und aus
   dem Über-Dialog. Damit bleibt der Preisblock unangetastet (§2).
5. **Ob ein Steuerberater dauerhaft mandatiert wird** oder nur für ein
   Erstgespräch. Bei Einzelunternehmen mit EÜR und Kleinunternehmerregelung
   genügt lange ein jährliches Gespräch.
