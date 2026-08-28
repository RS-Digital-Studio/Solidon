# Konzept: Monatliche Förderung in drei Stufen

Stand 23.08.2026, **überarbeitet am 24.08.2026 gegen die ersten Zugriffszahlen**
(§14), am selben Tag um eine **Nachkontrolle der Haftungsgrundlagen** ergänzt
(§15 — acht Befunde, zwei davon wirken heute), und am **28.08.2026 gegen vier
Festlegungen Roberts fortgeschrieben** (§16).
Beauftragt von Robert: ein Konzept für eine monatliche Finanzierung
„nebenbei, für Interessierte" in drei Stufen, bei der die höchste Stufe auch den
Lizenzschlüssel enthält — dazu eine Kontrolle aller Rechtstexte und eine
Recherche zur Rechtsform.

> **Der Auftrag hat sich am 28.08.2026 in einem Punkt geändert, und es ist der
> tragende:** Die höchste Stufe enthält **keinen Lizenzschlüssel** mehr. Die
> Förderung ist reine Unterstützung; der Lizenzkauf läuft getrennt davon. Wo
> dieses Dokument unterhalb von §16 vom Schlüssel in Stufe 3 spricht,
> beschreibt es einen überholten Stand — die Stellen sind einzeln markiert.

Dieses Dokument beantwortet drei Fragen, und sie hängen zusammen: **Was für ein
Modell** darf es sein, ohne das Kernversprechen der Marke zu brechen (§1–§4),
**welche Rechtsform und welche Pflichten** daraus folgen (§5–§9), und **welche
Rechtstexte** dafür geändert werden müssen — einschließlich der Fehler, die
heute schon darin stehen (§10).

> **Was die Überarbeitung geändert hat.** Die Zahlen der ersten fünf Tage haben
> zwei Empfehlungen widerlegt und eine dritte entschärft — das steht **an den
> betroffenen Stellen** und nicht nur im Nachtrag, damit das Dokument sich nicht
> selbst widerspricht:
>
> - **§2 und §4:** Die Förderung gehört in die **Anwendung**, nicht auf eine
>   Website-Seite. Damit ist auch „nichts am Code" hinfällig — es ist ein
>   Menüeintrag.
> - **§3:** Weg A bleibt empfohlen, aber seine Begründung trägt erst ab einer
>   Größenordnung, die noch nicht erreicht ist.
> - **§13:** Von den sechs Entscheidungen sind zwei beantwortet.

> **Was die Fortschreibung vom 28.08.2026 geändert hat** (§16), nach demselben
> Grundsatz — an den betroffenen Stellen, nicht nur im Nachtrag:
>
> - **§3 und §4:** Die Beträge sind **5 / 10 / 15 €** plus freier Betrag, und
>   **Stufe 3 enthält keinen Lizenzschlüssel mehr.** Damit fallen die
>   Lückenrechnung, Weg A gegen Weg B und die Handarbeit bei der
>   Schlüsselausgabe ersatzlos weg.
> - **§8:** Nicht ein Anbieter, sondern zwei. Der Lizenzkauf läuft über
>   **Lemon Squeezy**, die Förderung **nicht** — Merchant-of-Record-Anbieter
>   schließen Zuwendungen ohne Produkt vertraglich aus.
> - **Neu:** eine **Einmalspende** (§16.3), und sie ist der einfachste Teil des
>   Modells — eine Einmalzahlung ist kein Dauerschuldverhältnis.
> - **§13:** Von den drei verbliebenen offenen Entscheidungen sind zwei
>   erledigt; eine ist gegenstandslos geworden.

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

> **Seit dem 28.08.2026 gibt es diesen Schlüssel nicht mehr** (E2 in §16):
> Keine Förderstufe enthält eine Lizenz. Der Absatz bleibt stehen, weil er die
> Denkbewegung festhält, die zu E2 geführt hat — **die Trennung ist die
> konsequente Fortsetzung dessen, was hier schon angelegt war.** Wer den
> Schlüssel ohnehin nicht entziehen kann, hat ihn nie wirklich an die
> Förderung gekoppelt; E2 zieht daraus den Schluss und koppelt ihn auch
> nominell ab. Der Rest von §2 — fördern statt abonnieren — gilt unverändert
> und ist durch E2 nur eindeutiger geworden.

> Diese Linie ist unabhängig von mir zweimal erreicht worden: `3d-druck-bd` kam
> in ihrer Analyse des Kaufwegs am 23.08.2026 zum selben Ergebnis, aus derselben
> Codestelle heraus. Das erhöht das Vertrauen in die Schlussfolgerung, ersetzt
> aber die fachliche Prüfung in §5–§9 nicht.

### Wo die Förderung steht — in der Anwendung, nicht auf der Website

Der Verkaufsgrund auf `website/index.html:574` („Einmal, nicht jeden Monat")
bleibt **unberührt**. Er ist weiterhin wahr und weiterhin der stärkere Satz;
die Förderung wird nicht neben den Preisblock gestellt.

**Die erste Fassung dieses Konzepts empfahl dafür eine eigene Website-Seite,
verlinkt aus der Fußzeile. Die Zugriffszahlen vom 24.08.2026 haben das
widerlegt** (§14): Von 942 Seitenaufrufen entfielen **880 auf die Startseite**
und **27 auf `funktionen.html`** — etwa ein Dreißigstel, und das bei einer
Seite, die aus der Kopfzeile verlinkt ist.

> **Der Vergleich trägt, aber nur dieser eine.** `3d-druck-b8` hat am
> 24.08.2026 gemessen, dass **nur 12 der 30 Seiten den Zähler überhaupt
> einbanden** — es fehlten genau die erzeugten (Handbuch, Rechtstexte,
> KI-Seiten). Startseite und `funktionen.html` gehören beide zu den zwölf, der
> Vergleich 880 zu 27 ist also gültig. Eine Aussage darüber, wie oft Handbuch
> oder Rechtstexte gelesen werden, ist er **nicht** — diese Seiten hatten null
> Aufrufe, weil sie nicht zählten, nicht weil sie niemand las. **Eine Seite
> ohne Zähler und eine Seite ohne Leser sehen in der Auswertung gleich aus.**
> Behoben in `7cc0734`.

**Der richtige Ort ist die Anwendung selbst.** Drei Gründe, und sie sind
stärker als der Notbehelf, den sie ersetzen:

1. **Dort sind die Menschen, um die es geht.** 291 Downloads gegen 27 Aufrufe
   einer Unterseite: Wer das Programm benutzt, ist ein anderes Publikum als
   wer die Startseite überfliegt.
2. **Der Fördergedanke entsteht beim Benutzen, nicht beim Lesen.** „Ich mag
   dieses Werkzeug" ist ein Satz, den man nach der dritten Konstruktion sagt,
   nicht nach dreißig Sekunden auf einer Verkaufsseite.
3. **Es trennt Kauf und Förderung sauber.** Auf der Website steht der Preis,
   in der Anwendung steht das Angebot mitzutragen. Die Frage *„Ihr sagt kein
   Abo und bietet ein Abo an?"* stellt sich damit gar nicht erst an der Stelle,
   an der jemand über den Kauf nachdenkt.

Konkret: ein Eintrag unter **Hilfe**, in der Nachbarschaft von „Rückmeldung
senden" — nicht im Über-Dialog, den öffnet man einmal. Was er kostet, steht in
§4.

**Auf der Website bleibt genau ein Satz**, und zwar dort, wo er den Verdacht
ausräumt statt ihn zu wecken: in den AGB oder auf der Förderseite selbst, nicht
im Preisblock. Er muss sagen, dass die Förderung nichts freischaltet und nichts
abschaltet — sonst liest jemand „Abo" und hat recht.

---

## §3 Die drei Stufen

> **Überholt seit dem 28.08.2026 — die geltenden Stufen stehen in §16.1.**
> Robert hat die Beträge auf 5 / 10 / 15 € festgelegt und den Lizenzschlüssel
> aus Stufe 3 genommen. Dieser Abschnitt bleibt stehen, weil seine
> Begründungen es wert sind: Die Gebührenschwelle (unten), die Lückenrechnung
> und die drei Verbote am Ende erklären, **warum** die neuen Stufen so
> aussehen, wie sie aussehen. Was hier über den Schlüssel in Stufe 3 steht,
> gilt nicht mehr.

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

> **Gegenstandslos seit dem 28.08.2026 (E2 in §16).** Ohne Schlüssel in einer
> Förderstufe gibt es keine Lücke. Der Abschnitt bleibt als Begründung dafür
> lesbar, warum die Trennung von Förderung und Kauf die bessere Lösung war —
> er rechnet vor, was die Vermischung gekostet hätte.

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

**Empfehlung: Weg A — aber erst, wenn die Kaufrate bekannt ist.** Er ist
ehrlicher, einfacher und passt zu einem Modell, das ausdrücklich „für
Interessierte" gedacht ist und nicht als Vertriebskanal.

**Die Zahlen vom 24.08.2026 (§14) haben diese Empfehlung nicht gekippt, aber
ihre Begründung beschädigt.** Das Argument für Weg A lautete: „Wer 12 € zahlt,
um 57 € zu sparen, hätte ohnehin nicht gekauft." Das stimmt im Mittel — **und
es mittelt sich erst bei großen Zahlen.** Bei der heutigen Größenordnung
mittelt sich nichts:

| Annahme | Wert |
|---|---|
| Downloads in fünf Tagen | 291 |
| davon echte Interessenten (Doppelladungen abgezogen, geschätzt) | ~250 |
| übliche Demo-Kaufrate bei Kleinsoftware | 2–10 % |
| Käufer bei 5 % | **~12** |
| Umsatz bei 69 € | ~830 € |
| nehmen **drei** davon stattdessen Stufe 3 für einen Monat | 36 € statt 207 € |
| entgangen | **171 €, ein Fünftel des Jahresumsatzes** |

Bei tausend Käufern ist so etwas Rauschen. Bei zwölf ist es ein Fünftel, und
drei Einzelentscheidungen bestimmen das Ergebnis. **Die Kaufrate ist heute
nicht bekannt** — sie ist geschätzt, denn verkauft wurde noch nichts.

**Daraus folgt keine andere Empfehlung, sondern eine Reihenfolge:** Weg A
starten, **nachdem** der Verkauf läuft und die echte Kaufrate an ein paar
Wochen abgelesen ist. Liegt sie bei 2 %, ist die Lücke belanglos; liegt sie bei
10 %, ist Weg B ernsthaft zu prüfen. Diese Entscheidung für zwei Monate
offenzulassen kostet nichts — sie jetzt zu treffen hieße, sie auf einer
geschätzten Zahl zu treffen.

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

> **Teilweise überholt seit dem 28.08.2026.** Der Menüeintrag unten gilt
> unverändert und ist weiterhin der einzige Aufwand am Programm — dazu kommt
> mit Stufe 3 neu die Danksagungsliste im Über-Dialog (§16.6 Punkt 20).
> **Der Unterabschnitt „Der Schlüssel selbst" ist gegenstandslos:** Es wird
> für keine Förderstufe ein Schlüssel ausgegeben (E2 in §16).

**An der Lizenzprüfung nichts, an der Oberfläche ein Menüeintrag.** Das ist die
ganze Rechnung.

> **Die erste Fassung sagte hier „nichts am Code", und das war zu großzügig.**
> Es stimmte, solange die Förderung auf der Website stand. Seit §2 sie in die
> Anwendung verlegt — weil die Zugriffszahlen die Website-Variante widerlegt
> haben (§14) —, braucht es dort einen Weg dorthin. Der ist klein, aber er ist
> nicht null, und ein Konzept, das seinen eigenen Aufwand kleinrechnet, ist
> unbrauchbar.

**Was zu bauen ist:** ein Eintrag unter „Hilfe", neben „Rückmeldung senden",
der die Förderseite im Browser öffnet. Kein Dialog, kein Zustand, keine Abfrage
— ein Link mit `tr()`-Text und je einem Eintrag in den fünf Sprachkatalogen.
Er berührt weder `app/core` noch die Lizenzprüfung und fällt unter keine der
Ausschlüsse aus §12: Ein Link ist keine Funktion, die nur Förderern offensteht.

**Was ausdrücklich nicht gebaut wird:** kein Hinweis, der sich von selbst
meldet, keine Zählung, wie oft er geklickt wurde, und keine Unterscheidung
zwischen fördernden und nicht fördernden Installationen. Die Anwendung weiß
nicht, wer fördert, und soll es nicht wissen — das wäre der Server, den es
nicht gibt (§1).

### Der Schlüssel selbst

> **Gegenstandslos für die Förderung seit dem 28.08.2026 (E2 in §16).** Der
> Abschnitt bleibt stehen, weil zwei Feststellungen darin über den Anlass
> hinaus gelten: die Verwechslungsgefahr der **zwei Schlüsselpaare** und die
> Hauptversion als Wiederholungshebel. Für den **Kauf** über Lemon Squeezy
> (§16.4) beschreibt er weiterhin richtig, wie ein Schlüssel entsteht.

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

> **Argument 2 ist am 24.08.2026 nachkontrolliert worden und trägt in dieser
> Form nicht** (§15). Die EULA begrenzt nicht so sauber, wie hier
> vorausgesetzt: Nummer 11 nennt Erfüllungsgehilfen nicht, und eine
> AGB-Klausel, die gegen § 309 Nr. 7 BGB verstößt, fällt ganz statt teilweise
> (H1). Der Vergleich mit der GmbH ist zu grob — dort ist die Gesellschaft
> Herstellerin, persönlich haftet der Geschäftsführer erst über eine eigene
> Verkehrspflichtverletzung (H3). **Die Empfehlung bleibt**, sie steht auf
> Argument 1 und 3 — und auf der Versicherung, die dafür aus dem Nebensatz in
> die Aufgabenliste gehört (H4).

**Wenn eine Rechtsform gewechselt wird, dann später und aus einem konkreten
Anlass** — erster Angestellter, erster Großkunde mit eigenen Anforderungen,
Gewinn jenseits der 80.000 €.

### Die Wohnung als Betriebsstätte — muss der Vermieter zustimmen?

**Nachgetragen am 24.08.2026 auf Roberts Frage.** Das Formular der
Gewerbeanmeldung verlangt eine Betriebsstätte, und die ist hier die
Mietwohnung. Dieser Abschnitt fehlte.

**Kurz: nein, solange nichts nach außen tritt** — und zu informieren ist
niemand.

Die Schwelle zieht der BGH (Urteil vom 14.07.2009, VIII ZR 165/08): Eine
geschäftliche Tätigkeit, die **nach außen in Erscheinung tritt**, muss der
Vermieter ohne Vereinbarung nicht dulden. Er kann aber **nach Treu und Glauben
verpflichtet sein, sie zu erlauben**, wenn sie **ohne Mitarbeiter und ohne ins
Gewicht fallenden Publikumsverkehr** stattfindet. Die Darlegungslast dafür, dass
von der Nutzung keine stärkeren Einwirkungen ausgehen als von einer üblichen
Wohnnutzung, liegt beim **Mieter**.

Softwareentwicklung am Schreibtisch ist der Musterfall der zweiten Gruppe: kein
Schild, kein Kundenverkehr, kein Lärm, keine Anlieferungen, keine Mitarbeiter.
**Und das Gewerbeamt meldet nicht an den Vermieter** — es meldet an Finanzamt,
IHK und Berufsgenossenschaft.

**Drei Dinge trotzdem, und das erste vor der Anmeldung:**

1. **Den Mietvertrag lesen.** Formularverträge tragen häufig „Die Wohnung darf
   nur zu Wohnzwecken genutzt werden" oder einen ausdrücklichen
   Zustimmungsvorbehalt für Gewerbe. Solche Klauseln sind wirksam — der
   Anspruch auf Zustimmung aus Treu und Glauben besteht daneben, aber dann ist
   es ein Anspruch, den man geltend macht, und keine Selbstverständlichkeit.
   **Gehört zu §11 Punkt 6, und zwar davor.**
2. **Der eine Punkt, der wirklich nach außen tritt, ist das Impressum.** § 5 DDG
   verlangt eine **ladungsfähige** Anschrift; ein Postfach genügt nicht. Damit
   steht die Wohnadresse öffentlich im Netz, und zwar bevor der erste Euro
   fließt. Rechtlich reicht das nach überwiegender Auffassung nicht für eine
   Untersagung, solange am Haus nichts erkennbar ist — praktisch ist es der
   Weg, auf dem ein Vermieter es erfährt. Wer das nicht will, braucht eine
   ladungsfähige Geschäftsadresse (etwa 10 bis 30 € im Monat); bei einer
   erwarteten Größenordnung von einigen hundert Euro im Jahr (§14) ist das eine
   Abwägung und keine Empfehlung.
3. **Steuerlich ist es eine eigene Frage.** Das häusliche Arbeitszimmer nach
   § 4 Abs. 5 Nr. 6b EStG setzt voraus, dass es der **Mittelpunkt der gesamten**
   betrieblichen und beruflichen Tätigkeit ist — bei nebenberuflicher
   Selbstständigkeit neben einer Anstellung regelmäßig nicht. Dann bleibt die
   **Tagespauschale** von 6 € je Arbeitstag, höchstens 1.260 € im Jahr. Gehört
   ins Steuerberater-Gespräch (§11 Punkt 8), nicht in eine Selbsteinschätzung.

**Was hier ausdrücklich nicht steht:** ein Rat, den Vermieter vorsorglich zu
fragen. Eine Frage erzeugt eine Antwort, und eine abschlägige Antwort schafft
eine Lage, die ohne die Frage nicht bestand. Wenn der Mietvertrag schweigt und
die Tätigkeit unsichtbar bleibt, gibt es nichts zu genehmigen.

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
**139 Förderern in der höchsten Stufe über zwölf Monate** (bei 15 € nach E1,
§16.1) — zusätzlich zu allen Verkäufen, denn beides zählt zusammen.

### Ist die Förderung überhaupt umsatzsteuerbar? Ja, sicherheitshalber immer annehmen.

Die entscheidende Unterscheidung ist **echter gegen unechten Zuschuss**: Ohne
Gegenleistung liegt kein Leistungsaustausch vor und keine Umsatzsteuer an; mit
Gegenleistung schon.

- ~~**Stufe 3 ist eindeutig ein Leistungsaustausch.** Der Lizenzschlüssel ist
  eine konkrete Gegenleistung. Umsatzsteuerbar.~~ **Seit E2 (§16) gibt es
  keinen Schlüssel mehr** — damit fällt der eine eindeutige Fall weg, und
  **alle drei Stufen sind Grenzfälle.** Das macht die Frage nicht kleiner,
  sondern größer: §16.5 führt sie als die eine offene Frage dieses Modells
  aus, samt der Zange, die daraus für die Anbieterwahl entsteht.
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

> **Überholt seit dem 28.08.2026 — die geltende Aufteilung steht in §16.4.**
> Die Empfehlung unten, *einen* Merchant of Record für Kauf und Förderung zu
> nehmen, ist nicht umsetzbar: **Merchant-of-Record-Anbieter schließen
> Zuwendungen ohne Produkt vertraglich aus**, Lemon Squeezy ausdrücklich in
> seiner Liste verbotener Produkte. Es braucht zwei Anbieter — Lemon Squeezy
> für den Kauf (E4), eine Förderplattform für die Förderung. Die Begründung
> unten, **warum** ein MoR für den Verkauf richtig ist, gilt unverändert; sie
> trägt jetzt nur den Kauf und nicht mehr die Förderung.

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

> **Die Ableitung im ersten Satz trägt nicht mehr — die Folgen bleiben.**
> Seit E2 (§16) enthält keine Stufe einen Schlüssel, und schon H5 hatte
> gezeigt, dass die Pflichten ohnehin nicht am Schlüssel hängen: **Jede
> Gegenleistung genügt**, und Nennung wie Werkstattbrief sind welche. Der
> Kündigungsbutton bleibt deshalb Pflicht, die Widerrufsbelehrung für
> Dauerschuldverhältnisse ebenfalls. **Wo E2 wirkt, ist die Höhe des
> Einsatzes:** Ein Streitfall um eine Förderung von 15 € im Monat ohne
> Schlüssel wiegt anders als einer um eine Lizenz zu 69 €. Ob die Förderung
> überhaupt entgeltlich im Sinne dieser Vorschriften ist, ist die Frage aus
> §16.5 — **bis sie beantwortet ist, wird sie bejaht und der Button gebaut.**

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

> **Der letzte Halbsatz gilt seit dem 28.08.2026 nicht mehr für die
> Förderung** (§16.4): Sie läuft über einen Anbieter, der **kein** Merchant of
> Record ist. **Damit stellt Robert die Rechnung selbst** — unter der
> Kleinunternehmerregelung ohne Umsatzsteuerausweis und mit dem Hinweis nach
> § 19 UStG. Für den **Kauf** bleibt der Satz richtig; dort stellt Lemon
> Squeezy die Rechnung.

### 4. Was ausdrücklich nicht nötig ist

- **Keine Mindestlaufzeit** — und sie wäre auch nicht empfehlenswert. Seit 2022
  darf ein Verbrauchervertrag nach Ablauf der Erstlaufzeit höchstens auf
  unbestimmte Zeit verlängert werden, mit einer Kündigungsfrist von höchstens
  einem Monat. Eine Förderung, die man nicht sofort beenden kann, ist keine.
- **Keine Änderung am Code.** Siehe §4.

> **Diese Aufzählung ist unvollständig, nachkontrolliert am 24.08.2026**
> (§15). Sie leitet alles aus Stufe 3 ab, aber schon **Stufe 1 hat eine
> digitale Gegenleistung** und **Stufe 2 liefert Vorabversionen** — damit
> gelten die §§ 327 ff. BGB in der Fassung für **dauerhafte Bereitstellung**:
> Aktualisierungspflicht über die ganze Laufzeit, Beweislastumkehr über die
> ganze Laufzeit, Verjährung erst danach (H5). Und der Kündigungsbutton nach
> § 312k BGB verlangt eine **Webseite**, während §13 Nummer 6 die Förderung in
> die Anwendung gelegt hat — beides zusammen geht nicht auf (H6).

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
mit RS Digital oder mit Paddle.

> **Nachgetragen am 23.08.2026, nachdem `3d-druck-bd` den Befund schärfer
> gelesen hat als ich.** Ich hatte hier zunächst geschrieben, die
> Datenschutzerklärung „entscheide sich klar für Paddle" und sei damit die
> Vorlage, an der die AGB auszurichten seien. **Das war zu wohlwollend.** Sie
> nennt Paddle mit voller Anschrift als Empfänger personenbezogener Daten
> (`datenschutz.html:62–72`) — für eine Weitergabe, die nicht stattfindet und
> mangels Vertrag auch nicht stattfinden kann. Ein benannter Empfänger, an den
> nichts geht, ist nicht klar, sondern unzutreffend.
>
> **Und der Unterschied ist am Text messbar.** Die AGB tragen einen
> ausdrücklichen Vorbehalt — *„Solange nur die Demo-Version angeboten wird,
> greifen sie nicht."* Die Datenschutzerklärung trägt keinen: Sie schreibt
> *„Der Kauf läuft nicht über diese Website, sondern über den
> Zahlungsdienstleister Paddle"* im Präsens, als laufenden Vorgang. Von den
> beiden Texten ist also **die AGB der ehrlichere**, obwohl sie den
> Widerspruch enthält.

**Der Fix ist keine Textarbeit, sondern eine Entscheidung.** Denn heute gilt:

```
Kaufknopf auf solidon3d.de:   keiner
Paddle auf der Startseite:    kein Treffer
Verkauf:                      zu bis 30.10.2026 (store.py:50 DEMO_UNTIL)
Paddle-Konto:                 besteht nicht
```

Die AGB regeln einen Kaufvertrag, den derzeit niemand schließen kann, über
einen Anbieter, mit dem noch kein Vertrag besteht. **Den Widerspruch jetzt in
Richtung Paddle aufzulösen hieße, sich auf einen Anbieter festzulegen, den
Robert noch nicht gewählt hat** — und bei einer anderen Wahl wären danach zwei
Texte falsch statt einem.

| | Variante | Heute wahr? | Kosten |
|---|---|---|---|
| **1** | **MoR-Konstruktion ausschreiben** — Paddle schließt den Kaufvertrag und stellt die Rechnung, RS Digital räumt das Nutzungsrecht ein (EULA) | nein — verspricht einen Vertrag, den es nicht gibt | richtig, **sobald** Paddle beauftragt ist |
| **2** | **Keinen Anbieter nennen**, solange keiner beauftragt ist: beide Texte sprechen vom „Zahlungsdienstleister", der vor dem Kauf benannt wird | **ja**, und bleibt bei jeder Anbieterwahl wahr | beim Verkaufsstart muss jemand daran denken — gehört auf eine Verkaufsstart-Checkliste, die noch fehlt |

**Empfehlung: Variante 2.** Sie stimmt heute, nimmt keine Entscheidung vorweg
und macht aus einem Widerspruch keine zweite Festlegung. `3d-druck-bd` kommt
unabhängig zum selben Schluss.

> **Entschieden von Robert am 24.08.2026: Variante 2. Umgesetzt und erledigt.**
>
> Geändert wurde an drei Stellen, und die dritte war in beiden Vorlagen nicht
> genannt:
>
> - **`AGB.md` § 4** nennt keinen Anbieter mehr, sondern „einen
>   Zahlungsdienstleister. Welcher das ist, erfahren Sie vor dem Absenden der
>   Bestellung — mit Namen, Anschrift und den dort geltenden Bedingungen." Die
>   MoR-Konstruktion steht als **Bedingungssatz** da („Tritt dieser
>   Dienstleister als *Merchant of Record* auf, so wird er selbst
>   Vertragspartner des Kaufs…"), damit sie bei jeder Anbieterwahl stimmt.
> - **`AGB.md` § 3** löst damit auch den eigentlichen Widerspruch auf, der ohne
>   Anbieternamen sonst stehen geblieben wäre: „Wer beim Kauf Ihr
>   Vertragspartner ist, hängt vom Zahlungsdienstleister ab und wird Ihnen vor
>   dem Absenden der Bestellung angezeigt. Das Recht, die Software zu benutzen,
>   räumen Ihnen in jedem Fall wir ein." Vorher stand dort „wenn **wir** die
>   Bestellung annehmen" — eine Aussage, die bei einem MoR falsch ist.
> - **`website/datenschutz.html`, die Drittlandspassage.** Sie war
>   anbieterspezifisch und wäre sonst zu einer stehen gebliebenen Unwahrheit
>   geworden: Der Absatz begründete die Übermittlung mit dem
>   Angemessenheitsbeschluss **für das Vereinigte Königreich**. Ohne
>   feststehenden Anbieter gibt es kein Empfängerland, also auch keine
>   Rechtsgrundlage dafür. Jetzt steht dort, dass die Grundlage — Art. 45 oder
>   Art. 46 DSGVO — genannt wird, sobald der Dienstleister feststeht, und in
>   jedem Fall vor dem ersten Kauf.
>
> **Gegenprobe:** Der Name kommt in `AGB.md`, `EULA.md`, `WIDERRUF.md`, allen
> Seiten unter `website/` und `website/en/` nicht mehr vor. 95 Tests grün.
>
> **Was dadurch entsteht, ist eine Schuld auf den Verkaufstag** (§11 Nummer 10,
> §13). Die Texte sind jetzt dauerhaft wahr, aber unvollständig: Sie
> versprechen eine Angabe, die jemand nachtragen muss. Ohne
> Verkaufsstart-Checkliste ist das eine Zusage an den Kunden, die im Ablauf
> nirgends verankert ist.

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

- **`website/datenschutz.html`** ist handwerklich der beste der fünf Texte —
  **mit der Einschränkung aus B2**, die ihn an einer Stelle zum unehrlichsten
  macht: Er ist der einzige, der einen Vorgang im Präsens beschreibt, den es
  nicht gibt, und als einziger ohne Vorbehalt. Alles Übrige daran hält: Die
  Zählung ohne
  Cookie ist sauber begründet (Art. 6 Abs. 1 lit. f DSGVO, § 25 TDDDG korrekt
  verneint), der Auftragsverarbeitungsvertrag mit netcup ist genannt, die
  Drittlandsübermittlung nach UK ist mit dem Angemessenheitsbeschluss nach
  Art. 45 DSGVO richtig behandelt, und die drei Netzverbindungen der Anwendung
  sind vollständig und ehrlich beschrieben.
- **`EULA.md` Nummern 10 und 11** (Haftung) sind fachlich solide aufgebaut:
  Kardinalpflichten, unbeschränkte Haftung bei Vorsatz und grober
  Fahrlässigkeit, Produkthaftungsgesetz, ausdrücklicher Ausschluss für
  sicherheitskritische Anwendungen. Das ist die Grundlage der Empfehlung in §5.

  > **Im Aufbau richtig, im Wortlaut nicht — nachkontrolliert am 24.08.2026**
  > (§15). Nummer 11 nennt **Erfüllungsgehilfen und gesetzliche Vertreter
  > nicht**, und Nummer 10 ist eine negative Beschaffenheitsvereinbarung, die
  > gegenüber Verbrauchern nach § 327h BGB **ausdrücklich und gesondert** zu
  > vereinbaren wäre — nicht in einem Vertragstext, sondern im Bestellvorgang.
  > Beides ist Formulierungs- und Ablaufarbeit, keine inhaltliche Kehrtwende;
  > dieser Punkt ist damit **nicht mehr „in Ordnung"**, sondern H1 und H8.
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

> **Erledigt am 23.08.2026 durch `3d-druck-bd` (`3ccc72f`).** Die
> Gebührenrechnung in `:266` ist korrigiert — 3,5 % von 69 € sind 2,42 €, nicht
> 1,72 €. Die **anderen vier** Stellen mit 49 € bleiben stehen, und das ist
> richtig: Sie zitieren den Stand vom 06.08. und sind als Bestandsaufnahme
> korrekt. Ein Dokument, das seinen Stichtag beschreibt, wird nicht dadurch
> besser, dass man es nachträglich auf heute umschreibt.

---

### B8 — Der Entwurfsvermerk hängt am Erzeuger, nicht am Rechtsstatus

**Gefunden von `3d-druck-bd` am 24.08.2026, nachgemessen.**

```
agb.html          Entwurfsvermerk: ja
eula.html         Entwurfsvermerk: ja
widerruf.html     Entwurfsvermerk: ja
datenschutz.html  Entwurfsvermerk: NEIN
impressum.html    Entwurfsvermerk: NEIN
```

Die Ursache ist `DOCUMENTS` in `tools/make_legal.py:38`: Drei Dateien stehen
darin, und `draft_banner()` setzt den Vermerk bei jeder. Die beiden anderen
kommen durch einen anderen Kanal auf die Seite und **können ihn gar nicht
bekommen**, wie vorläufig ihr Inhalt auch sei.

**Die Datenschutzerklärung stand also nicht ohne Vorbehalt da, weil jemand sie
für fertig hielt, sondern weil sie von Hand gepflegt wird.** Das ist kein
Versehen an einer Stelle, sondern eine Lücke im Verfahren.

**Beim Impressum ist der fehlende Vermerk richtig** — eine Tatsachenangabe
braucht keinen, und einer dort würde Zweifel an Pflichtangaben säen, die es
nicht gibt.

**Bei der Datenschutzerklärung wäre er aber ebenfalls falsch, und hier weiche
ich von `3d-druck-bd`s Empfehlung ab.** Sie schlug vor, den Vermerk von Hand zu
setzen. Dagegen spricht die Natur des Textes: Eine Datenschutzerklärung ist
keine Klausel, sondern eine **Pflichtinformation nach Art. 13 DSGVO**, und
Art. 12 verlangt sie „in präziser, transparenter, verständlicher und leicht
zugänglicher Form". Ein Text, der sich selbst als ungeprüften Entwurf
bezeichnet, untergräbt genau die Eigenschaft, die er haben muss. Bei AGB und
EULA ist der Vermerk ein sichtbar gemachter interner Vorbehalt; bei einer
Pflichtinformation entwertet er die Information selbst.

**Gemacht wurde deshalb das, was das eigentliche Problem löst:** Der Abschnitt
„Der Kauf einer Lizenz" trägt jetzt denselben Vorbehalt wie die AGB — *„Solange
nur die Demo-Version angeboten wird, findet nichts davon statt."* Damit ist die
unzutreffende Präsens-Behauptung aus B2 entschärft, **ohne** die Anbieterfrage
vorwegzunehmen und **ohne** die Pflichtinformation zu entwerten. Der Name
Paddle bleibt stehen; ob er bleibt, entscheidet §13 Punkt 6.

**Offen bleibt die Verfahrenslücke.** Solange
`datenschutz.html` von Hand gepflegt wird, gilt für sie keine der
Automatiken aus `make_legal.py` — weder der Entwurfsvermerk noch der
Platzhalter-Mechanismus, der ihn beim Eintragen der Anschrift von selbst
entfernt. Eine `DATENSCHUTZ.md` als Quelle würde das heilen; das ist eine
Umstellung und keine Aufgabe für heute, aber sie gehört ins Register.

## §11 Was zu tun ist

Reihenfolge nach Dringlichkeit, nicht nach Aufwand.

| # | Was | Wo | Wann |
|---|---|---|---|
| 1 | **ODR-Verweis streichen** (B1) | `AGB.md` § 10 | **sofort**, unabhängig vom Fördermodell |
| 2 | **Konverter-Escaping reparieren** (B3) | `tools/make_legal.py:76` | vor dem nächsten Website-Upload |
| ~~3~~ | ~~**Vertragspartner-Widerspruch auflösen** (B2)~~ — **erledigt am 24.08.2026**, Variante 2 | `AGB.md` §§ 3–4, `website/datenschutz.html` | — |
| 4 | **Impressum ergänzen** (B5) | `website/impressum.html` | mit der Gewerbeanmeldung |
| 5 | **EULA-Nummerierung** (B4) | `EULA.md` | bei der nächsten Fassung |
| 6 | Gewerbe anmelden, Geschäftskonto, USt-IdNr. | Gewerbeamt Bamberg, Bank, BZSt | vor dem ersten Geldeingang |
| 7 | Krankenkasse und ggf. Arbeitgeber schriftlich informieren | — | vor dem ersten Geldeingang |
| 8 | Steuerberater-Erstgespräch mit diesem Dokument | — | vor dem ersten Geldeingang |
| ~~9~~ | ~~Paddle: Subscriptions einrichten, Kündigungsbutton klären~~ — **ersetzt am 28.08.2026 durch die Punkte 17 bis 19** (§16.6): der Merchant of Record trägt jetzt nur den Kauf, die Förderung läuft über einen zweiten Anbieter | — | — |
| 10 | Förderseite bauen, Kündigungsbutton, Widerrufsbelehrung für Dauerschuldverhältnisse | `website/`, `AGB.md`, `WIDERRUF.md` | vor dem Start der Förderung |

**Punkt 1 bis 5 sind Textarbeit und in einer Sitzung zu erledigen.** Punkt 6 bis
9 sind Roberts Entscheidungen und Behördengänge; sie stehen hier, damit keiner
davon vergessen wird.

> **Sechs weitere Punkte (11 bis 16) sind am 24.08.2026 aus der Nachkontrolle
> der Haftungsgrundlagen hinzugekommen** — die Tabelle dazu steht am Ende von
> §15. Zwei davon sind neu in dieser Liste und nicht bloß Textarbeit: die
> **Produkthaftpflicht mit Software-Einschluss** (Punkt 13), auf der nach H3
> und H4 die Rechtsformentscheidung ruht, und das **Häkchen im Bestellvorgang**
> nach § 327h BGB (Punkt 14), von dem die Wirksamkeit von `EULA.md` Nummer 10
> gegenüber Verbrauchern abhängt. Punkt 12 gilt **heute** und nicht erst zum
> Verkaufsstart.

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

Alles andere in diesem Dokument ist begründet und ausgearbeitet. Diese Punkte
sind Geschäftsentscheidungen und keine fachlichen.

**Zwei davon haben die Zugriffszahlen vom 24.08.2026 beantwortet** (§14) — sie
stehen unten als erledigt, nicht gestrichen, weil die Begründung Bestand hat.

### Offen

1. ~~**Die Beträge** — 3 / 7 / 12 € sind ein begründeter Vorschlag, kein
   Ergebnis.~~ **Entschieden am 28.08.2026: 5 / 10 / 15 € plus freier Betrag**
   (E1). Ausgeführt in §16.1, samt der Gebührenrechnung, die zeigt, warum die
   alte Untergrenze von 3 € damit ihre Bedeutung verliert.
2. ~~**Weg A oder Weg B** bei der Schlüsselausgabe in Stufe 3 (§3).~~
   **Gegenstandslos seit dem 28.08.2026** (E2): Keine Stufe gibt einen
   Schlüssel aus, also gibt es keine Lücke zu schließen. Diese Entscheidung
   muss nicht mehr auf die Kaufrate warten — was sie zugleich vom
   Verkaufsstart am 01.11.2026 entkoppelt (§16.8).
3. **Ob ein Steuerberater dauerhaft mandatiert wird** oder nur für ein
   Erstgespräch. Bei Einzelunternehmen mit EÜR und Kleinunternehmerregelung
   genügt lange ein jährliches Gespräch.
### Von Robert entschieden

4. ~~**Variante 1 oder 2 beim Vertragspartner-Widerspruch** (B2).~~
   **Variante 2 am 24.08.2026, umgesetzt.** Weder AGB noch
   Datenschutzerklärung nennen noch einen Anbieter; beide sprechen vom
   „Zahlungsdienstleister", der vor dem Kauf benannt wird. Einzelheiten in B2 —
   darunter die anbieterspezifische Drittlandspassage, die in beiden Vorlagen
   nicht genannt war und ohne Anpassung als Unwahrheit stehen geblieben wäre.

### Durch die Zahlen beantwortet

5. ~~**Ob die Förderung jetzt startet** oder erst nach dem Verkaufsstart.~~
   **Nach dem Verkaufsstart.** Nicht wegen der Reichweite, sondern wegen des
   Apparats: Gewerbeanmeldung, Geschäftskonto, USt-IdNr., Steuerberater,
   Kündigungsschaltfläche, Widerrufsbelehrung fallen **identisch** an, ob fünf
   oder fünfhundert Menschen fördern. Nach dem Verkaufsstart trägt der Verkauf
   sie ohnehin; davor müsste die Förderung sie allein rechtfertigen — bei einer
   erwarteten Größenordnung von einigen hundert Euro im Jahr (§14).
6. ~~**Wo die Förderseite steht** — Startseite oder eigene Seite.~~ **Weder
   noch: in der Anwendung.** Von 942 Seitenaufrufen gingen 880 auf die
   Startseite und 27 auf `funktionen.html`. Eine Seite in der Fußzeile hätte
   keine Leser; die 291 Menschen, um die es geht, sitzen vor dem Programm und
   nicht vor der Website. Ausgeführt in §2, der Aufwand dafür in §4.

> **Und ein Punkt, der auf keine dieser Listen passt, aber existiert: eine
> Verkaufsstart-Checkliste gibt es nicht.** Variante 2 in B2 verschiebt
> Textarbeit auf den Tag des Verkaufsstarts, und mehrere Punkte aus §11 tun
> dasselbe — der Entwurfsvermerk auf den drei Rechtstexten, die USt-IdNr. im
> Impressum, der Name des Zahlungsdienstleisters in zwei Texten. Ohne eine
> Liste, die an diesem Tag gelesen wird, sind das drei Gelegenheiten, etwas zu
> vergessen. Sie anzulegen ist eine halbe Stunde und gehört zur Demo-Phase,
> nicht zum Fördermodell — deshalb steht sie hier als Hinweis und nicht als
> Aufgabe.

---

## §14 Was die ersten Zahlen sagen

Nachgetragen am 24.08.2026. Robert hat die Auswertungsseite
(`solidon3d.de/api/stats.php`) vorgelegt; die Zahlen unten sind daraus
abgelesen und gegengerechnet — die Tagestabelle summiert sich exakt auf die
drei Kopfzahlen (942 / 766 / 291).

### Was gemessen wurde

| Tag | Aufrufe | Besuche | Downloads | Downloads je Besuch |
|---|---:|---:|---:|---:|
| 24.08. *(läuft noch)* | 79 | 58 | 15 | 25,9 % |
| **23.08.** | **804** | **694** | **265** | **38,2 %** |
| 22.08. | 18 | 4 | 3 | *(4 Besuche)* |
| 21.08. | 3 | 1 | 1 | *(1 Besuch)* |
| 20.08. | 38 | 9 | 7 | *(9 Besuche)* |
| **Summe** | **942** | **766** | **291** | 38,0 % |

**Die Messung läuft fünf Tage, nicht einen Monat.** Die Seite überschreibt das
mit „im Monat", aber der erste gezählte Tag ist der 20.08. Wer die 291
Downloads als Monatswert liest, liest zu niedrig.

**Und eine Zahl trägt fast alles:** Der 23.08. stellt 91 % der Downloads und
91 % der Besuche. Die drei Tage davor haben zusammen **14 Besuche** — daraus
lässt sich nichts rechnen, und die 75 % bzw. 100 % in der Tabelle sind
Artefakte kleiner Zahlen, keine Quoten.

### Der eine belastbare Befund

**38,2 % der Besucher am 23.08. haben heruntergeladen.** Bei
Software-Landingpages sind 2–10 % üblich. Das ist die wichtigste Zahl des
ganzen Abschnitts, und sie ist belastbar, weil sie auf 694 Besuchen beruht.

Wer auf dieser Seite landet, will das Programm. Das Problem ist nicht die
Überzeugungskraft der Seite — es ist, dass zu wenige sie sehen.

Der 24.08. liegt mit 25,9 % darunter. Der Tag lief beim Ablesen noch; ob die
Quote sinkt oder Downloads nachkommen, entscheidet sich später. **Aus einem
laufenden Tag wird kein Trend abgeleitet.**

### Was daraus für dieses Konzept folgt

| Befund | Folge | Wo |
|---|---|---|
| 880 von 942 Aufrufen auf `/`, 27 auf `funktionen.html` | Die Förderung gehört in die **Anwendung**, nicht auf die Website. Eine Fußzeilen-Seite hätte keine Leser. | §2, §4, §13 Punkt 6 |
| Größenordnung: einige hundert Euro im Jahr | Der Verwaltungsapparat fällt unabhängig davon an. Also **nach** dem Verkaufsstart, wenn der Verkauf ihn ohnehin trägt. | §13 Punkt 5 |
| ~12 erwartete Käufer im ersten Jahr | Bei so kleinen Zahlen mittelt sich die Kannibalisierung nicht weg. Weg A bleibt empfohlen, aber **erst nach zwei Wochen echtem Verkauf**. | §3 |
| 291 Downloads, 25.000 € Kleinunternehmergrenze | Rechtsform und Steuerempfehlung **bestätigt**, nicht in Frage gestellt. | §5, §6 |

### Zwei Nebenbefunde, die anderswo hingehören

**Die Plattformverteilung**, gerechnet über alle 291 Downloads:

| | Downloads | Anteil |
|---|---:|---:|
| Windows (`.exe`) | 235 | 80,8 % |
| Linux (`.flatpak`) | 41 | 14,1 % |
| macOS (`.pkg`) | 15 | 5,2 % |

Für das Fördermodell belanglos, für die **Signierfrage** nicht: Die
SmartScreen-Warnung eines unsignierten Windows-Pakets trifft vier von fünf
Interessenten. Das ist ein Argument in `konzept-demo-2026-10.md`, nicht hier —
es steht nur da, weil die Zahl sonst nirgends steht.

**Und 271 der 291 Downloads gingen auf Fassungen vor 0.1.4**, die inzwischen
vom Server entfernt sind. Das ist kein Fehler, sondern der Update-Weg: Diese
Installationen erfahren über `version.json`, dass es etwas Neueres gibt. Es
bedeutet aber, dass ein Rückschritt der Versionsnummer 271 Installationen
beträfe — der Grund, warum `tools/upload_website.py` sich weigert, eine
unsignierte `version.json` hochzuladen.

### Die Frage, die diese Zahlen nicht beantworten

**Woher kam der 23.08.?** 694 Besuche an einem Tag, davor 1, 4 und 9. Ob das
ein wiederholbarer Kanal war oder ein einmaliges Strohfeuer, entscheidet über
das Fördermodell mehr als jede Zahl hier: **Ein Modell, das auf wiederkehrende
Zuwendung setzt, braucht wiederkehrende Aufmerksamkeit.** Bleibt es bei einem
Peak, ist die Förderung ein netter Zusatz zum Verkauf; wiederholt sich der
Kanal monatlich, ist sie ein tragender Teil.

**Und die Antwort steht nicht in den eigenen Daten, obwohl der Datenschutztext
sie verspricht.** Ich hatte hier zunächst geschrieben, sie stehe auf der
Auswertungsseite unterhalb von „Seiten" — **das war falsch, und es ist ein
Fehlbefund derselben Sorte wie oben.** `3d-druck-b8` hat am 24.08.2026
nachgewiesen, dass die Liste „Woher" nicht kaputt, sondern **strukturell leer**
war: Der Zähler-Beacon trägt als `Referer` immer die eigene Seite, und
`referrer_host()` verwarf sie völlig zu Recht — ein echter Verweis kam nie an.

```
alt   {"k":"p","v":"/","r":""}
neu   {"k":"p","v":"/","r":"www.google.com"}
```

Die Seite erklärte sich das selbst mit „Suchmaschinen schicken ihre Herkunft
oft nicht mehr mit" — plausibel und falsch. Behoben in `212c086`.

**Für die Vergangenheit ist die Frage damit endgültig unbeantwortbar**: Die
Daten wurden nie erhoben, und keine spätere Auswertung holt sie zurück. Ab dem
nächsten Upload entstehen sie. Für ein Modell, das auf wiederkehrende Zuwendung
setzt, ist das die wichtigste Zahl — und sie fängt bei null an.

Wenn Robert weiß, wo am 23.08. über Solidon geschrieben wurde, ist das heute
die einzige Quelle dafür.

> **Diese Zahlen altern schnell.** Sie beschreiben fünf Tage, von denen einer
> alles trägt. Wer im Oktober hier liest, prüft sie nach, statt sie zu
> übernehmen — das ist die Hausregel dieser Sammlung, und hier gilt sie
> besonders.

---

## §15 Nachkontrolle der Haftungsgrundlagen (24.08.2026)

Beauftragt von Robert: die Haftungsgrundlagen des Modells noch einmal prüfen.
Geprüft wurden `EULA.md` Nummern 4a, 10, 11, `AGB.md` §§ 7 und 8 und die
Haftungsaussagen dieses Dokuments in §5 Nummer 2, §8 und §9.

**§10 B6 nannte `EULA.md` 10 und 11 „fachlich solide aufgebaut". Das ist im
Aufbau richtig und im Wortlaut unvollständig** — und dieser Wortlaut trägt die
Rechtsformentscheidung in §5. Acht Befunde, die ersten beiden wirken heute.

### H1 — Die Haftungsklausel nennt Erfüllungsgehilfen nicht (`EULA.md` Nr. 11)

Der Text sagt „**wir** haften unbeschränkt bei Vorsatz und grober
Fahrlässigkeit" und schließt danach „eine weitergehende Haftung" aus.
§ 309 Nr. 7 lit. b BGB verlangt aber, dass grobes Verschulden **eines
gesetzlichen Vertreters oder Erfüllungsgehilfen** ebenfalls nicht ausgeschlossen
wird; lit. a verlangt dasselbe für Körperschäden bereits bei einfacher
Fahrlässigkeit.

Wer die Klausel eng liest, findet dort einen Ausschluss, den § 309 verbietet.
Und AGB-Klauseln werden nicht geltungserhaltend reduziert: **Wenn sie fällt,
fällt sie ganz** — es gilt dann die volle gesetzliche Haftung, also das
Gegenteil dessen, was §5 Nummer 2 annimmt.

**Fix, fünf Wörter je Absatz:** „bei Vorsatz und grober Fahrlässigkeit — auch
unserer gesetzlichen Vertreter und Erfüllungsgehilfen". Kein inhaltliches
Zugeständnis, sondern die Formulierung, die den Schutz überhaupt erst hält.

### H2 — Der einzige heute wirkende Haftungstext ist der schwächste (`EULA.md` Nr. 4a)

`AGB.md` erklärt sich selbst für die Demo-Zeit außer Kraft, der Verkauf ist bis
30.10.2026 zu. **Damit ist Nummer 4a die einzige Haftungsregelung, die jetzt
gilt** — und sie hat zwei Fehler auf drei Zeilen:

- *„Wir haften für Vorsatz und grobe Fahrlässigkeit"* schließt Körperschäden
  bei einfacher Fahrlässigkeit aus. § 309 Nr. 7 lit. a BGB lässt das nicht zu,
  auch nicht bei unentgeltlicher Überlassung — die Vorschrift knüpft an die
  AGB gegenüber Verbrauchern an, nicht an ein Entgelt.
- Der Nachsatz *„im Übrigen gelten die Abschnitte 10 und 11 entsprechend"*
  widerspricht dem: Nummer 11 gewährt für Körperschäden gerade unbeschränkte
  Haftung. Zwei Sätze, zwei Aussagen — das ist neben § 309 auch eine Frage des
  Transparenzgebots (§ 307 Abs. 1 Satz 2 BGB).

Dazu die Prämisse: **Eine Demo ist keine Schenkung.** Sie wird zur
Absatzförderung überlassen, nicht aus Freigebigkeit; das Haftungsprivileg des
§ 521 BGB ist damit nicht selbstverständlich zu haben.

**Fix:** Den Satz ersatzlos durch „Für die Haftung gelten die Nummern 10 und
11" ersetzen. Er gibt ein Privileg auf, das ohnehin unsicher war, und beseitigt
den Widerspruch mit.

### H3 — Die Produkthaftung wächst genau zum Verkaufsstart

Dieses Dokument behandelt Produkthaftung als bekannte, feststehende Größe. Sie
ist es nicht mehr: **Richtlinie (EU) 2024/2853** löst die Richtlinie von 1985
ab, Umsetzungsfrist **9. Dezember 2026**, anzuwenden auf Produkte, die danach
in Verkehr gebracht werden. Was sich ändert:

- **Software ist ausdrücklich ein Produkt** — der bisherige Streit darüber
  entfällt.
- Ersatzfähig werden auch **Datenverlust und -zerstörung** sowie Schäden an
  privat genutzten Sachen; der Selbstbehalt von 500 € entfällt.
- Fehlerhaftigkeit kann sich aus **unterbliebenen Sicherheitsaktualisierungen**
  ergeben, also aus einem Unterlassen nach dem Verkauf.
- **Abbedingen lässt sie sich nicht** — sie ist deliktisch und wirkt gegenüber
  jedem Geschädigten, nicht nur gegenüber dem Vertragspartner. `EULA.md`
  Nummer 10 kann die Sicherheitserwartung prägen; ausschließen kann sie nichts.

**Zeitlage:** Demo bis 30.10.2026, Verkauf danach (§13 Nummer 5). Der erste
Verkauf fällt damit aller Voraussicht nach **unter das neue Recht**. Der
deutsche Umsetzungsstand ist am Verkaufstag zu prüfen und nicht heute zu
unterstellen.

### H4 — Die Versicherung trägt die Rechtsformentscheidung und steht in keiner Liste

§5 Nummer 2 begründet das Einzelunternehmen unter anderem damit, dass eine
**Berufshaftpflicht für IT** „besser und billiger als eine Rechtsform" hilft.
In §11 stehen zehn Aufgaben, in §13 sechs Entscheidungen — **die Versicherung
kommt in keiner von beiden vor.** Das Argument, das die Entscheidung stützt,
ist nirgends eine Handlung.

Dazu inhaltlich: Eine IT-Berufshaftpflicht deckt typischerweise
**Vermögensschäden**. Personen- und Sachschäden aus einem fehlerhaften Produkt
gehören in eine **Produkthaftpflicht mit ausdrücklichem Software-Einschluss** —
das ist ein anderer Baustein, und nach H3 der wichtigere. Zu fragen ist
außerdem, ob die Police Schäden aus **KI-gestützten Ausgaben** einschließt und
wie sie mit den in Nummer 10 ausgeschlossenen Einsatzgebieten umgeht: Versichert
sein muss der Fall, dass der Kunde sich **nicht** daran hält.

### H5 — Die Förderung löst mehr aus als §9 nennt: §§ 327 ff. BGB

§9 leitet alle Pflichten aus Stufe 3 ab („sobald Stufe 3 den Schlüssel
enthält") und nennt Kündigungsbutton, Widerruf, Preisangaben. **Schon Stufe 1
hat eine digitale Gegenleistung** — Zugang zur Änderungsliste vor der
Veröffentlichung —, **Stufe 2 liefert Vorabversionen.** Beides sind digitale
Produkte gegen Entgelt in **dauerhafter Bereitstellung**, und dafür gilt die
schärfere Variante der §§ 327 ff. BGB:

| Vorschrift | Folge bei Dauerbereitstellung |
|---|---|
| § 327f | Aktualisierungspflicht über den **gesamten** Bereitstellungszeitraum, nicht nur den erwartbaren |
| § 327e Abs. 3 | objektive Anforderungen: übliche Beschaffenheit — die eine Vorabversion begriffsnotwendig nicht immer erfüllt |
| § 327h | eine Abweichung davon wirkt nur, wenn der Verbraucher **eigens** in Kenntnis gesetzt wurde und sie **ausdrücklich und gesondert** vereinbart ist |
| § 327k Abs. 2 | Beweislastumkehr für den **gesamten** Zeitraum statt für ein Jahr |
| § 327j Abs. 2 | Verjährung frühestens zwölf Monate **nach Ende** der Bereitstellung |
| § 327s | Abweichungen zum Nachteil des Verbrauchers sind unwirksam |

**Wer für 7 € im Monat Vorabversionen zusagt, schuldet mangelfreie
Vorabversionen** — mit Nacherfüllung und Minderung. Das ist das Gegenteil
dessen, was eine Vorabversion ist.

**Zwei Wege:** Stufe 2 auf etwas zurücknehmen, das keine digitale Leistung ist
— oder die Abweichung nach § 327h formal sauber vereinbaren, mit einem eigenen
Häkchen im Bestellvorgang, nicht mit einem Satz in der EULA. §3 macht es beim
Wunschkanal bereits richtig („kein Anspruch"); hier fehlt dieselbe Sorgfalt.

### H6 — Der Kündigungsbutton steht gegen „Förderung in der Anwendung"

§9 Nummer 1 verlangt eine Schaltfläche, die **ständig verfügbar, ohne Anmeldung
und unmittelbar erreichbar** ist; § 312k Abs. 2 BGB spricht von einer
Schaltfläche **auf der Webseite**. §13 Nummer 6 hat am 24.08.2026 entschieden:
keine Förderseite auf der Website, sondern ein Menüeintrag in der Anwendung.
**Beide Aussagen stehen unverbunden nebeneinander.**

Eine Schaltfläche in einem Programm, das man deinstallieren kann, ist nicht
ständig verfügbar — und wer gekündigt hat, weil ihm das Programm nicht gefiel,
hat es als Erstes gelöscht. Dazu verspricht Stufe 1 eine **Nennung auf der
Förderseite**, die es nach §13 Nummer 6 nicht gibt: eine geschuldete Leistung
ohne Ort.

**Das widerruft die Entscheidung nicht, es ergänzt sie.** Die Website-Seite
wird gebraucht, aber nicht als Werbeseite: als Rechtsseite mit Kündigung,
Bedingungen und Nennung. Geworben wird weiter in der Anwendung — das war der
Befund aus den Zahlen und der bleibt.

### H7 — Beim Merchant of Record läuft die Freistellung in die Gegenrichtung

§8 zählt auf, was ein MoR abnimmt: Umsatzsteuer, Rechnung, Widerruf,
Streitfälle. Das stimmt. **Nicht genannt ist die Kehrseite.** MoR-Verträge
enthalten regelmäßig eine **Freistellungsklausel** zulasten des Verkäufers,
häufig der Höhe nach unbegrenzt, nach ausländischem Recht und mit ausländischem
Gerichtsstand. Was der MoR gegenüber dem Kunden trägt, holt er sich beim
Verkäufer zurück — und `EULA.md` Nummer 11 wirkt gegenüber dem Kunden, nicht
gegenüber dem MoR.

Für ein Einzelunternehmen mit Haftung aus dem Privatvermögen ist das **die
größte vertragliche Haftungsübernahme des ganzen Modells**, und sie steht in
einem Vertrag, den noch niemand gelesen hat. Gehört zu §11 Nummer 9: vor der
Unterschrift die Freistellungs- und Haftungsklauseln lesen und hier festhalten.

### H8 — Drei kleinere Punkte, gleicher Anlass

- **`EULA.md` Nr. 11, letzter Satz** sagt „die gesetzlichen Mängelrechte **beim
  Kauf**". Bei digitalen Produkten sind es die §§ 327 ff. BGB, nicht das
  Kaufrecht — der Vorbehalt liest sich enger als die Gesetzeslage. `AGB.md` § 7
  hat es richtig; die EULA zieht nicht nach.
- **`EULA.md` Nr. 10 ist eine negative Beschaffenheitsvereinbarung.** Inhaltlich
  ist sie die eigentliche Risikobegrenzung von Solidon — kein Prüfinstitut,
  keine zugesicherte Maßhaltigkeit, keine tragenden Teile. Gegenüber
  Verbrauchern hängt ihre Wirksamkeit an derselben Formalie wie in H5
  (§ 327h BGB): eigens in Kenntnis gesetzt, ausdrücklich und gesondert
  vereinbart. **Das betrifft den Verkauf, nicht nur die Förderung** — und es
  ist ein Häkchen im Bestellvorgang, kein Abschnitt in einem Vertragstext.
- **`AGB.md` § 8** verweist für die Haftung auf `EULA.md` Nr. 11. Tritt der
  Zahlungsdienstleister als MoR auf, gelten für den Kauf seine Bedingungen
  (so § 4 selbst) — der Verweis läuft dann teilweise leer. Klarstellen, dass er
  die Überlassung der Software betrifft.

### Was das für §5 und §11 heißt

**Die Empfehlung Einzelunternehmen kippt nicht.** Argument 1 (Aufwand) und
Argument 3 (späterer Wechsel) stehen unverändert. Aber **Argument 2 trägt in
seiner heutigen Form nicht**: Die EULA begrenzt nicht so sauber wie
angenommen (H1), und der Vergleich mit der GmbH ist zu grob. Bei einer
Kapitalgesellschaft ist die **Gesellschaft** Herstellerin; persönlich haftet
der Geschäftsführer erst über eine eigene Verkehrspflichtverletzung nach
§ 823 BGB. Bei einem Einzelunternehmen haftet Robert von der ersten Minute an
persönlich, ohne Zwischenstufe. Der Unterschied ist nicht null — er ist der
zwischen Regel und Ausnahme.

**Damit trägt die Empfehlung allein auf der Versicherung** (H4), und die ist
bisher ein Nebensatz. Sie gehört in §11, vor den ersten Geldeingang.

### Ergänzung zu §11

| # | Was | Wo | Wann |
|---|---|---|---|
| 11 | **Erfüllungsgehilfen in die Haftungsklausel** (H1) | `EULA.md` Nr. 11 | mit Punkt 5, bei der nächsten Fassung |
| 12 | **Demo-Haftung auf Nr. 10/11 verweisen** (H2) | `EULA.md` Nr. 4a | **sofort** — sie gilt heute |
| 13 | **Produkthaftpflicht mit Software-Einschluss** anfragen, Deckung und Prämie (H3, H4) | Versicherer | vor dem ersten Geldeingang |
| 14 | **§ 327h-Häkchen im Bestellvorgang** für Nr. 10 und für Vorabversionen (H5, H8) | Bestellstrecke | vor dem Verkaufsstart |
| 15 | **Rechtsseite auf der Website** — Kündigung, Bedingungen, Nennung (H6) | `website/` | vor dem Start der Förderung |
| 16 | **Freistellungsklausel des MoR lesen** und hier festhalten (H7) | Dienstleistervertrag | vor der Unterschrift |

**Was hier nicht geprüft wurde**, weil es nicht Haftung ist: die
KI-Verordnung. Ihre Transparenzpflichten (Art. 50) gelten seit dem 02.08.2026;
für einen Chat, der „KI-Chat" heißt und mit dem Schlüssel des Nutzers gegen
dessen Anbieter läuft, greift die Ausnahme „offensichtlich". Erwähnt, damit
niemand denkt, sie sei übersehen worden.

> **Und dieselbe Einschränkung wie ganz oben:** Das ist recherchiert und mit
> Fundstellen belegt, aber es ist keine Rechtsberatung. H1, H2 und H5 sind
> Formulierungsfragen, die ein Fachanwalt in einer halben Stunde entscheidet.
> H3 und H4 sind es nicht — das sind Geschäftsrisiken mit einer Frist im
> Dezember.

---

## §16 Die Fortschreibung vom 28.08.2026 — Beträge, Stufen ohne Schlüssel, Einmalspende

Robert hat am 28.08.2026 vier Festlegungen getroffen. Drei davon beantworten
offene Punkte aus §13, die vierte ist neu:

| # | Festlegung | Wirkt auf |
|---|---|---|
| **E1** | Die Beträge sind **5 / 10 / 15 €** im Monat, dazu ein **frei wählbarer Betrag** | §13 Nummer 1 |
| **E2** | **Kein Lizenzschlüssel in einer Förderstufe.** Die Förderung ist reine Unterstützung | §3, §4, §13 Nummer 2 |
| **E3** | Zusätzlich eine **Einmalspende** | neu — §16.3 |
| **E4** | Der **Lizenzkauf** läuft über **Lemon Squeezy**, sobald die Demo endet | §8 |

**E2 ist die folgenreichste, und sie vereinfacht mehr, als sie wegnimmt.** Mit
dem Schlüssel fällt die ganze Lückenrechnung aus §3 weg: kein Weg A gegen
Weg B, keine Nähe zum Teilzahlungsgeschäft nach § 507 BGB, keine Handarbeit bei
der Schlüsselausgabe (§4), keine Frage, ob ein Förderer den Kauf unterläuft.
Die Förderung und der Verkauf berühren sich nicht mehr. Was §1 als Konflikt
beschrieb, ist damit nicht nur entschärft, sondern aufgelöst.

### §16.1 Die drei Stufen und der freie Betrag

Beträge von Robert, Namen und Inhalte als Vorschlag. Stufe 3 hieß bisher
**Schlüssel** — der Name trägt nicht mehr, weil kein Schlüssel mehr darin ist.

| | Name | Betrag | Was zurückkommt |
|---|---|---|---|
| **1** | **Rückenwind** | **5 € / Monat** | Nennung auf der Unterstützerseite (freiwillig, Name oder Pseudonym). Der **Werkstattbrief**. |
| **2** | **Werkbank** | **10 € / Monat** | Alles aus Stufe 1. Dazu die Änderungsliste, bevor die Version herauskommt, und ein Kanal für Wünsche — ausdrücklich **ohne Anspruch** auf Umsetzung. |
| **3** | **Fundament** | **15 € / Monat** | Alles aus Stufe 2. Dazu die **Nennung im Über-Dialog der Anwendung**, in der jeweils nächsten Version. |
| — | **Freier Betrag** | ab 5 € | Ordnet sich der höchsten erreichten Stufe zu: 12 € bekommen Werkbank, 20 € bekommen Fundament. |

**Der Werkstattbrief** ist der Vorschlag, der am wenigsten kostet und am besten
zum Projekt passt: eine unregelmäßige Notiz per E-Mail darüber, was gebaut
wurde und was dabei schiefging — im Ton der Commit-Meldungen dieses
Repositories, die ohnehin Erzählungen sind und keine Etiketten.
**Ausdrücklich ohne zugesagte Frequenz** („wenn es etwas zu erzählen gibt",
nicht „monatlich"). Eine zugesagte Frequenz wäre eine geschuldete Leistung mit
Termin; eine unregelmäßige Notiz ist es nicht.

**Die Nennung im Über-Dialog ist der eigentliche Fund für Stufe 3.** Sie ist
dauerhaft, sie steht im Produkt statt auf einer Seite, die niemand aufruft
(§14 hat genau das gemessen), und sie kostet in der Pflege eine Zeile je
Förderer. Vor allem ist sie **keine Leistung an den Förderer**, sondern eine
Nennung über ihn — das ist der Unterschied, an dem §16.4 hängt. Die
Formulierung „in der jeweils nächsten Version" ist bewusst gewählt: Sie sagt
zu, dass der Name aufgenommen wird, nicht dass eine Version zu einem Termin
erscheint.

**Warum diese Beträge tragen.** Die alte Begründung für 12 € („ein halbes Jahr
übersteigt den Kaufpreis") ist mit E2 gegenstandslos — es gibt nichts mehr
gegenzurechnen. Die neuen Beträge stehen auf einer anderen Rechnung, und sie
geht auf:

| | 5 € | 10 € | 15 € |
|---|---|---|---|
| Gebühr Ko-fi Gold, 5 % (§16.4) | 0,25 € | 0,50 € | 0,75 € |
| Zahlungsgebühr, grob 0,25 € + 2,5 % | 0,38 € | 0,50 € | 0,63 € |
| **kommt an** | **~4,37 €** | **~9,00 €** | **~13,62 €** |
| Anteil, der ankommt | 87 % | 90 % | 91 % |

Die alte Untergrenze von 3 € war mit der Gebührenschwelle begründet. **5 € hebt
diese Schwelle von einem Argument zu einer Nebensache** — der Anteil, der
ankommt, ist auf allen drei Stufen nahe beieinander. Damit entscheidet der
Förderer nach dem, was er geben will, und nicht danach, wo die Gebühr am
wenigsten frisst.

**Der freie Betrag hat einen praktischen Vorbehalt.** Bei
Mitgliedschaftsplattformen sind die Stufen in der Regel feste Beträge; ein frei
wählbarer *monatlicher* Betrag ist nicht überall vorgesehen (bei GitHub
Sponsors ja, bei Ko-fi-Mitgliedschaften nicht ohne Weiteres). **Vor dem Start
beim gewählten Anbieter prüfen.** Fällt er weg, ist der Verlust klein: Der
freie Betrag wirkt vor allem bei der Einmalspende (§16.3), und dort kann ihn
jede Plattform.

### §16.2 Was die Stufen weiterhin nicht enthalten dürfen

Die drei Verbote aus §3 gelten unverändert — keine Funktion, die es ohne
Förderung nicht gibt; kein Anspruch auf Support; keine Mitsprache über „wird
gelesen" hinaus. **Ein viertes kommt mit E2 hinzu:**

- **Kein Lizenzschlüssel und kein Rabatt darauf, in keiner Stufe.** Sonst ist
  die Förderung doch ein Vertriebsweg, und die ganze Rechnung aus §3 kommt
  zurück. Wer fördert und die Software behalten will, kauft sie wie jeder
  andere.

**Und eine Streichung gegenüber dem alten §3: Vorabversionen sind nicht mehr
vorgesehen.** Sie standen dort in Stufe 2, und H5 hat gezeigt, was sie
auslösen: Wer für Geld Vorabversionen zusagt, schuldet **mangelfreie**
Vorabversionen, mit Nacherfüllung und Minderung über die gesamte Laufzeit
(§ 327f, § 327k Abs. 2 BGB). Das ist das Gegenteil dessen, was eine
Vorabversion ist. An ihrer Stelle steht in Stufe 2 die Änderungsliste vorab —
ein Text, keine Software.

> Wer Vorabversionen trotzdem will, braucht das § 327h-Häkchen aus §11
> Nummer 14, und zwar als eigenes Häkchen im Bestellvorgang, nicht als Satz in
> einem Vertragstext. Das ist machbar, aber es ist eine Bestellstrecke, die
> eine Förderplattform so nicht anbietet.

### §16.3 Die Einmalspende

**Frei wählbarer Betrag mit drei Vorschlägen — 3 €, 10 €, 25 € —, keine
wiederkehrende Zahlung, keine Gegenleistung.** Sie ist der einfachste Teil des
ganzen Modells, und zwar aus einem Grund, der leicht übersehen wird: **Eine
Einmalzahlung ist kein Dauerschuldverhältnis.**

Damit entfällt genau das, was die Förderung teuer macht:

| | Förderung (monatlich) | Einmalspende |
|---|---|---|
| Kündigungsbutton § 312k BGB | Pflicht (§9) | entfällt — nichts zu kündigen |
| Widerrufsbelehrung für Dauerschuldverhältnisse | nötig | entfällt |
| §§ 327 ff. BGB in der Dauerbereitstellungsvariante | greifen (H5) | greifen nicht |
| Aktualisierungspflicht über die Laufzeit | ja | keine Laufzeit |

**Empfehlung: die Einmalspende ohne jede Gegenleistung anbieten** — auch ohne
Nennung. Dann ist sie eine Schenkung, kein Leistungsaustausch, und die Frage
aus §16.5 stellt sich für sie gar nicht erst. Wer genannt werden will, fördert
monatlich; das ist nebenbei ein Grund, von der Spende zur Förderung zu wechseln.

> **Diese Empfehlung ist nicht neu, sie wird hier nur eingelöst.** §6 hat den
> Satz schon am 23.08.2026 geschrieben, als es noch keine Einmalspende gab:
> „Wer echte Spenden ohne jede Gegenleistung will, muss sie **getrennt** und
> ohne Stufen anbieten — dann aber ohne Nennung, ohne Vorabzugang, ohne
> alles." E3 ist genau dieses „getrennt und ohne Stufen".

**Die Alternative — Nennung auch für Einmalspender ab einem Betrag — ist
möglich, aber sie zieht die Spende in dieselbe Behandlung wie die Förderung.**
Der Gewinn (etwas mehr Anreiz) steht gegen den Verlust (der einfachste Fall des
Modells wird zum komplizierten). Dafür spricht wenig.

**Was auf keinen Fall passieren darf:** die Einmalspende als „Vorbestellung",
„Frühbucher" oder „schon mal etwas anzahlen" darstellen. Sobald ein Kunde
darin eine Anzahlung auf die Lizenz lesen kann, ist es eine — mit
Rückforderungsanspruch, wenn nicht geliefert wird. Der Satz auf der Seite muss
das ausschließen, und zwar mit denselben Worten wie bei der Förderung: **Sie
schaltet nichts frei und rechnet auf nichts an.**

### §16.4 Die Anbieterfrage — und warum es zwei sein müssen

Hier steht der harte Befund dieser Fortschreibung. **§8 empfahl Paddle für
alles. Das geht nicht mehr, und es ginge auch mit Lemon Squeezy nicht.**

**Lemon Squeezy schließt Spenden vertraglich aus.** In der Liste der verbotenen
Produkte stehen Zuwendungen, denen kein Produkt gegenübersteht oder deren Preis
über dem Produktwert liegt. Genau das ist eine Förderung ohne Gegenleistung,
und genau das ist eine Spende. Lemon Squeezy prüft außerdem jeden Store vor der
Freischaltung. Ein Store, der beides anbietet, kommt entweder nicht durch oder
wird später gesperrt — **und das Zweite wäre erheblich schlimmer als das
Erste**, weil dann der Verkauf mit stillsteht. Für Paddle und FastSpring gilt
dasselbe der Sache nach: Ein Merchant of Record ist gebaut, um Produkte zu
verkaufen, und braucht eins.

**Daraus folgt die Aufteilung:**

| Was | Anbieter | Warum |
|---|---|---|
| **Lizenzkauf** | **Lemon Squeezy** (E4) | Merchant of Record: schuldet die Umsatzsteuer im Land des Käufers, meldet sie, stellt die Rechnung. Das ist die Begründung aus §8, und sie gilt unverändert |
| **Förderung + Einmalspende** | **nicht Lemon Squeezy** — Ko-fi, Steady oder GitHub Sponsors | dort ist eine Zuwendung ohne Produkt vorgesehen statt verboten |

**Zur Wahl beim zweiten Anbieter**, gemessen an diesem Modell:

| | Einmalig | Monatlich | Gebühr | Einschätzung |
|---|---|---|---|---|
| **Ko-fi** | ja | ja, mit Gold | 0 % einmalig; Gold 6 $/Monat, 5 % auf Mitgliedschaften | **empfohlen** — deckt beide Fälle, die Einmalspende ohne Provision |
| Steady | ja | ja | nicht verifiziert | deutscher Anbieter, deutsches Recht — vor einer Entscheidung die Gebühren erfragen |
| GitHub Sponsors | ja | ja, freier Betrag | 0 % für Privatkonten | kann als Einziger den freien Monatsbetrag, ist aber auf offenen Quelltext zugeschnitten — Solidon3D ist es nicht |

**Zwei Vorbehalte zu E4, die zu Punkt 9 und 16 aus §11 gehören:**

- **Lemon Squeezy ist seit Juli 2024 Teil von Stripe**, und seit 2026 gibt es
  daneben **Stripe Managed Payments** — gebaut vom selben Team, zu denselben
  Konditionen von 5 % zuzüglich 0,50 $, und vom Lemon-Squeezy-Geschäftsführer
  selbst als das Ziel bezeichnet, auf das Bestandskunden wechseln sollen. Ein
  Abschaltdatum ist nicht genannt, Neuanmeldungen laufen. **Das ist kein Grund
  gegen E4, aber einer, den Umzug von vornherein einzuplanen:** keine
  Lemon-Squeezy-Kennung in einer Projektdatei, in einem Rechtstext oder im
  Lizenzschlüssel verankern, die einen Wechsel teuer macht. Die
  Bestellkennung im Schlüssel (`key.py:90`, Feld `order`) ist davon nicht
  betroffen — sie ist eine Zeichenkette ohne Anbieterbezug.
- **Die Freistellungsklausel aus H7 gilt für Lemon Squeezy genauso** wie für
  Paddle. Sie ist die größte vertragliche Haftungsübernahme des Modells und
  vor der Unterschrift zu lesen.

### §16.5 Die eine Frage, die diese Fortschreibung nicht beantworten kann

**Ab wann ist ein Dank eine Gegenleistung?** Daran hängt mehr als eine
Formulierung — es entscheidet, ob die Förderung überhaupt umsatzsteuerbar ist,
und damit, ob der zweite Anbieter (der **kein** Merchant of Record ist) tragfähig
bleibt.

Die Skala, von harmlos nach heikel:

| Was zurückkommt | Leistungsaustausch? |
|---|---|
| gar nichts (Einmalspende nach §16.3) | nein — Schenkung |
| Nennung des Namens, schlicht | **strittig** — bloßer Dank spricht dagegen, werbewirksame Hervorhebung mit Verlinkung dafür (Sponsoring) |
| Werkstattbrief per E-Mail | eher ja — eine auf elektronischem Weg erbrachte sonstige Leistung |
| Änderungsliste vorab, Wunschkanal | ja |
| Vorabversionen | ja, und dazu H5 |

**Die Zange, die daraus entsteht:** Je mehr die Stufen enthalten, desto eher ist
es ein Umsatz — und desto eher bräuchte es einen Merchant of Record, der die
Umsatzsteuer im Land des Förderers abführt. **Genau der nimmt aber keine
Förderung an** (§16.4). Bei digitalen Leistungen an Verbraucher in der EU gilt
das Bestimmungslandprinzip, und ohne MoR bedeutet das eine OSS-Registrierung
beim Bundeszentralamt für Steuern.

**Zwei Auswege, und der zweite ist der empfohlene:**

**Variante A — die Stufen so mager halten, dass es kein Umsatz ist.** Nur
Nennung, sonst nichts. Sauber, aber die Stufen sind dann kaum noch
unterscheidbar, und der Werkstattbrief — der beste Teil des Vorschlags — fällt
weg.

**Variante B — die Stufen wie in §16.1 lassen und die Umsatzsteuerbarkeit
annehmen.** Das ist ohnehin die Haltung, die §6 dieses Dokuments schon
einnimmt („sicherheitshalber immer annehmen"). **Solange die
Kleinunternehmerregelung nach § 19 UStG trägt, kostet diese Annahme nichts** —
es wird keine Umsatzsteuer ausgewiesen und keine abgeführt. Erst wenn die
Grenze reißt, wird die Frage teuer, und dann steht ohnehin eine Umstellung an.

**Empfehlung: Variante B**, mit der Frage in der Mappe für das
Steuerberatergespräch aus §11 Nummer 8. Sie lautet konkret: *Sind Nennung und
unregelmäßiger Werkstattbrief bei einer monatlichen Förderung ein
Leistungsaustausch — und falls ja, wie ist die Leistung bei Förderern im
EU-Ausland zu behandeln, wenn die Plattform kein Merchant of Record ist?*

### §16.6 Was zusätzlich zu tun ist

Anschluss an die Tabelle in §11; die Nummerierung läuft dort weiter.

| # | Was | Wo | Wann |
|---|---|---|---|
| 17 | **Zweiten Anbieter wählen** und prüfen, ob er einen freien Monatsbetrag kann (§16.1, §16.4) | Ko-fi / Steady | vor dem Start der Förderung |
| 18 | **Kündigungsbutton beim zweiten Anbieter klären** — die Frage aus §8 stellt sich für ihn, nicht mehr für den MoR | Anbieter | vor dem Start der Förderung |
| 19 | **Lemon Squeezy einrichten** für den Lizenzkauf, Freistellungsklausel lesen (H7), Umzugsrisiko notieren (§16.4) | Lemon Squeezy | vor dem Verkaufsstart |
| 20 | **Über-Dialog um eine Danksagungsliste ergänzen** (Stufe 3) | `app/ui/` | erst, wenn es Förderer gibt |
| 21 | **Frage zum Leistungsaustausch** in die Steuerberater-Mappe (§16.5) | — | mit Punkt 8 |

**Punkt 20 ist der einzige Code in diesem ganzen Konzept außer dem Menüeintrag
aus §4** — und er wird erst gebraucht, wenn jemand Stufe 3 nimmt. Bis dahin ist
das Fördermodell reine Website- und Behördenarbeit.

### §16.7 Was damit aus §13 wird

| §13 | Stand nach dieser Fortschreibung |
|---|---|
| 1. Die Beträge | **entschieden: 5 / 10 / 15 €** plus freier Betrag (E1) |
| 2. Weg A oder Weg B | **gegenstandslos.** Ohne Schlüssel in einer Stufe gibt es keine Lücke, die man schließen könnte (E2). Die Frage muss nicht mehr auf die Kaufrate warten |
| 3. Steuerberater dauerhaft oder einmalig | **weiterhin offen** — §16.5 gibt dem Erstgespräch eine Frage mehr mit |

Damit ist von den sechs Punkten in §13 einer offen, und es ist der, der
ohnehin nur Robert beantworten kann.

### §16.8 Der Zeitplan, den das voraussetzt

§13 Nummer 5 hat entschieden, dass die Förderung **nach** dem Verkaufsstart
beginnt — nicht wegen der Reichweite, sondern weil Gewerbeanmeldung,
Geschäftskonto, USt-IdNr. und Steuerberater identisch anfallen, ob fünf oder
fünfhundert Menschen fördern. **Dieses „nach" hat inzwischen ein Datum.**

Auskunft von Robert am 28.08.2026, über die Parallelsitzung am Update-Weg:
Die Demo endet am **30.10.2026**, bis dahin kommen weitere Updates, und ab dem
**01.11.2026** wird verkauft. Die Demoversion wird dabei nicht ersetzt — sie
wird zur Vollversion mit dem vierzehntägigen Testlauf davor.

Daraus ergibt sich die Reihenfolge, in der die Punkte aus §11 und §16.6 fällig
werden:

| Bis wann | Was | Woher |
|---|---|---|
| **sofort, unabhängig vom Modell** | ODR-Verweis (1), Konverter-Escaping (2), Demo-Haftung (12) | §11, §15 |
| **vor dem 01.11.2026** | Gewerbe, Konto, USt-IdNr. (6), Krankenkasse (7), Steuerberater (8), Versicherung (13), § 327h-Häkchen (14), Impressum (4), Lemon Squeezy samt Freistellungsklausel (19) | §11, §16.6 |
| **nach dem 01.11.2026, wenn der Verkauf läuft** | zweiter Anbieter (17), Kündigungsbutton bei ihm (18), Rechtsseite (15), Widerrufsbelehrung für Dauerschuldverhältnisse (10) | §16.6, §11 |
| **wenn es Förderer gibt** | Danksagungsliste im Über-Dialog (20) | §16.6 |

**Der Fördermodell-Teil ist damit der zweite Block, nicht der erste.** Was vor
dem 01.11. liegt, liegt dort ohnehin — für den Verkauf. Die Förderung erbt
diesen Apparat, statt ihn allein rechtfertigen zu müssen, und das war die
Begründung von §13 Nummer 5.

> **Diese Tabelle ist für das Fördermodell vollständig und für den 01.11.
> nicht.** Der Verkaufsstart trägt außerdem einen **Auslieferungsschritt**, und
> ohne ihn sperrt die Verkaufsversion am ersten Tag genau die Menschen aus, um
> die es hier geht. Gemessen von der Sitzung am Update-Weg am 28.08.2026 und
> hier am Code nachgeprüft: Der Umschalter ist eine Zeile
> (`store.py:77`, `DEMO_UNTIL` → `None`), aber **beide Zweige schreiben
> denselben Testlaufmarker**. `trial_days_left()` rechnet danach
> `used = heute − erster Demo-Start`; ein Marker vom 20.08.2026 ergibt am
> 01.11. **null von vierzehn Tagen**, während ein Neukunde vierzehn bekommt.
> Robert hat entschieden, dass die vierzehn Tage laufen sollen, ohne
> Umgehungsmöglichkeit; gebaut wird es als `SALE_FROM` analog zu `DEMO_FROM`.
>
> **Für dieses Konzept ist das kein eigener Punkt** — es ist Verkaufsarbeit und
> wird dort erledigt. Es steht hier, weil die Zeile darüber sonst suggeriert,
> der 01.11. sei ein reiner Behörden- und Rechtstermin. Und weil ein
> Registerpunkt daran hängt: „AGB § 2 beschreibt vierzehn Tage, die für die
> Demo nicht gelten" löst sich am 01.11. **nicht von selbst** auf, sondern nur
> mit diesem Schritt.

> **Eine Annahme dieses Dokuments ist damit überholt und wird hier
> ausdrücklich als solche markiert:** §14 rechnet mit einer geschätzten
> Kaufrate, weil „verkauft wurde noch nichts". Ab dem 01.11.2026 ist sie
> messbar. Für E2 spielt sie keine Rolle mehr — die Lückenrechnung, für die
> sie gebraucht wurde, ist mit dem Schlüssel weggefallen (§16.7). Sie bleibt
> interessant für die Frage, wie prominent die Förderung beworben wird.
