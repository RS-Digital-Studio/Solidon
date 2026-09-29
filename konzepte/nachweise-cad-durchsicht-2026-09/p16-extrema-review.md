# P1.6 — unabhängige Prüfung der Facettenextrema

Lesende mathematische Gegenprüfung vom 20.09.2026 zu
`p16-extrema-plan.md` und `p16-contract.md`. Produkt und Testbestand bleiben
eingefroren. Geschrieben wurde ausschließlich diese Notiz. Ergänzend lief
eine kleine arithmetische Prüfung über Python-Standardeingabe, ohne
Dateiartefakte, Fenster, pytest-Sammlung oder Leistungsprüfung.

## Ergebnis

**Die angegebenen Kandidaten sind in reeller Arithmetik vollständig.**
Für den gerichteten Kreiskegel fehlt kein isoliertes glattes Innenmaximum;
für den Ringtorus fehlen neben Kanten/Achse keine weiteren glatten
Innenkandidaten. Die horizontale Torusebene und degenerierte Dreiecke sind
zu Recht eigene Fälle. Keine fachliche Schwelle muss dafür gelockert werden.

**Die numerische Zertifizierung ist noch nicht geschlossen.** Der Plan nennt
die richtigen Anforderungen, legt aber die entscheidenden ausführbaren
Beweisbausteine noch nicht fest: gerichtete Rechnung einschließlich Winkel
und Rahmen, Behandlung nur möglicher Kandidaten, sichere Originalzeugen
und eine endliche Schranke, solange eine dieser Prüfungen offen bleibt.
Die bisherigen Raster-/SLSQP-Sonden können diese Teile nicht ersetzen.

Die kleinste robuste Umsetzung ist: ein gemeinsamer begrenzter
Intervall-Punktabstand, analytische Kandidaten als Beschleunigung, zertifizierte
eindimensionale Kantenverfeinerung und stets eine gültige globale
Lipschitz-Schranke. Eine flächendeckende Unterteilung jedes Dreiecks ist
weiterhin nicht erforderlich. Erreicht die begrenzte Rechnung ihre
Zielbreite nicht, wird das wirkliche Restintervall ausgewiesen.

## 1. Gerichteter Kegel: Herleitung bestätigt, Zweig vereinfachbar

Mit `rho>=0`, `0<alpha<pi/2`, `s=sin(alpha)`, `c=cos(alpha)`:

```
H = s*z - c*rho
t = s*rho + c*z
```

Der gefüllte Vorwärtskegel ist `K={H>=0}`. Dort gilt `t>=0` und der Abstand
zur Oberfläche ist `H`. Außerhalb ist der nächste Oberflächenpunkt entweder
die Mantelprojektion oder die Spitze. Der Abstand zum konvexen Körper K
ist konvex und hat auf einem Dreieck sein Maximum an mindestens einer Ecke.
Daher ist die Zerlegung des Plans richtig:

```
max_T d_surface = max(max_Ecken d_K, max_T H, 0)
```

Ein glattes inneres Maximum von H setzt sich entlang einer Geraden in der
Meridianebene bis zum Dreiecksrand oder zur Achse fort, weil H auf jeder
achsenseitig festen Meridianhälfte affin ist. Fällt die ganze Dreiecksebene
mit einer Meridianebene zusammen, gilt dieselbe Aussage unmittelbar in
dieser Halbebene. Diese entartete Ebenenüberschneidung ergänzt die kurze
Begründung des Plans; sie erzeugt keinen weiteren Kandidatentyp.

Die Kantenableitung und die angegebene geschlossene Lösung sind korrekt.
Zusätzlich für die numerische Einhüllung nutzbar:

```
H''(u) = -c*Delta/rho(u)**3       für rho>0
```

Damit ist H auf jeder glatten Kante konkav, und eine enthaltene Nullstelle
von H' ist das eindeutige innere Maximum, abgesehen von affinen Abschnitten.
Bei Achsenschnitt bleibt der Knick als Kandidat erforderlich. Ein
Achsenintervall braucht für H nur seinen größten z-Wert.

**Kleine praktische Verbesserung:** Der Punktabstand benötigt keinen
unsicheren numerischen Test `t>=0`:

```
d_surface = hypot(H, min(t, 0))
d_K       = hypot(min(H, 0), min(t, 0))
```

Für `t>=0` ergibt sich `abs(H)` beziehungsweise der äußere Anteil; für
`t<0` ist H negativ und `H²+t²=rho²+z²`, also der Abstand zur Spitze.
Das hält die gerichtete Nappe auch bei Punkten hinter der Spitze ein und
ist für Intervallrechnung günstiger. Der Mittelpunkt eines Features ist
dabei kein Ersatz für die wirkliche Kegelspitze.

## 2. Ringtorus: Kandidaten vollständig, Grenzen der Aussage

Nur `R>r>0` ist hier belegt. Horn-/Spindeltori dürfen nicht mit derselben
Abstandsinterpretation durch einen großzügigen Radienvergleich gelangen.
Für den Ringtorus ist der Abstand zur Oberfläche tatsächlich

```
q = hypot(rho-R, z)
d = abs(q-r)
```

Da das stetige F=q² auf dem zusammenhängenden Dreieck ein Intervall als
Bild hat, genügt für den größten Betrag der Abweichung einer seiner beiden
Endwerte F_min/F_max. Die Umrechnung des Plans ist daher richtig.

**Kanten:** Für Delta>0 haben die angegebenen zweiten Ableitungen höchstens
zwei Nullstellen, weil rho² eine verschobene positive Quadratik ist.
Die daraus folgenden höchstens drei monotonen Abschnitte von F' decken
alle stationären Punkte ab. Berührende Nullstellen an Abschnittsgrenzen
müssen erhalten bleiben. Bei Delta=0 ist der Achsenknick ein gesonderter
Grenzpunkt; bei A=0 bleibt eine Quadratik. Eine Punktkante kann konstant
sein und hat dann nicht „höchstens drei“ stationäre Punkte, benötigt aber
auch nur eine Auswertung, wie der Plan bereits vorsieht.

**Innere glatte Punkte:** In der gedrehten Ebene mit `n=(a,0,b)`, a>0,
erzwingt die Lagrange-Bedingung

```
y*(1-R/rho)=0.
```

Für y=0 ergibt sich auf der richtigen radialen Halbebene das Minimum der
Quadratik `(x-sigma*R)²+z²` unter der Ebenenbedingung: genau `p_sigma`.
Für rho=R folgt wegen a>0 zunächst der Multiplikator null und dann z=0:
genau die höchstens zwei Mittelkreisschnittpunkte. `sigma*x>0` ist eine
echte Bereichsbedingung, kein frei wählbarer Achsensinn. Die Grenze x=0
gehört zum gesonderten Achsenfall.

Für F_max genügen sogar Kanten und Achse: Auf der Geraden in jeder
Meridianhälfte ist F streng konvex; ein glattes ausschließlich inneres
Maximum kann dort nicht liegen. Die vier inneren Kandidaten sind für
F_min erforderlich. Diese Trennung spart Arbeit, ohne Fälle zu verlieren.

Für a=0 entsteht eine ganze stationäre Kreislinie. Die Radiusintervall-
Lösung der horizontalen Ebene ist vollständig. Für b=0 darf `h/b` nicht
berechnet werden: Bei h ungleich null existiert kein Achsenschnitt, bei
h=0 muss das ganze enthaltene Achsenintervall behandelt werden. Dies sind
geometrische Aussagen; „kleines b“ ist nicht automatisch der zweite Fall.

## 3. Offene Beweisbausteine vor einer konservativen Zahlenzusage

### 3.1 Gerichtete Rechnung beginnt vor dem letzten Funktionswert

`nextafter` um einen abschließenden NumPy-/libm-Wert ist kein allgemeiner
Fehlerbeweis. Beispiel in der unabhängigen arithmetischen Prüfung:

```
(1e16 + 1.0) - 1e16              -> 0.0
nextafter(0.0, +inf)              -> 5e-324
exakte Summe der Eingabe-Floats    -> 1.0
```

Der Plan verlangt bereits gerichtete Grundoperationen; genau das muss
implementiert und getrennt geprüft werden. Gerichtete Addition,
Subtraktion, Multiplikation, Division, Quadrat und Wurzel müssen alle
Zwischenwerte umfassen. Dot/Cross mit Auslöschung dürfen nicht erst nach
einer beliebigen BLAS-Reduktion um ein ULP erweitert werden. Division durch
ein Intervall mit null liefert keine scheinbar endliche Kandidatenzahl.
Skalierte Normen vermeiden unnötigen Über-/Unterlauf.

Eine sichere sqrt-Klammer lässt sich durch nach außen gerundetes Quadrieren
überprüfen und nötigenfalls erweitern. Dasselbe Prinzip gilt für die
positive Kubikwurzel der Torus-Wendepunkte. Ein gerundetes Produkt zum
Vergleich ohne eigene Fehlerhülle wäre wieder derselbe Zirkelschluss.

**Winkel:** Ein bloßes `sin/cos` plus angenommenes ULP-Budget ist hier noch
nicht belegt. Eine kleine Lösung ohne neue Abhängigkeit ist die begrenzte
alternierende Taylorrechnung auf dem ohnehin gültigen Intervall
`[0,pi/2]`, mit gerichtet gerechneten Termen und dem ersten ausgelassenen
Term als Restgrenze. Der inzwischen konkretisierte Trägervertrag speichert
`half_angle` bereits in Radiant. Der Kartenrechner wertet diesen gespeicherten
float-Winkel aus und braucht deshalb keine eigene Grad→Radiant-Umrechnung
oder pi-Multiplikation. Diese Rechnung erfolgt einmal je Träger, nicht je
Dreieck. Die Zielgröße ist der bereits gespeicherte Trägerwinkel, keine
neue Schätzung seines Ursprungswinkels.

**Rahmen:** Ein von NumPy normalisierter float-Rahmen ist nicht allein
deshalb beweisbar orthonormal. Kleine Achsen-/Lagefehler werden bei großen
Koordinaten verstärkt. Der gemeinsame Punktabstand kann das Problem ohne
neuen geometrischen Fit in Weltkoordinaten vermeiden:

```
w   = p-centre_or_apex
z   = dot(w, axis)/norm(axis)
rho = norm(cross(w, axis))/norm(axis)
```

Alles mit Intervallen aus den ursprünglichen float-Eingaben. Der gedrehte
Rahmen bleibt für schnelle Kandidaten sinnvoll; seine Kandidaten müssen
aber die wirkliche Ebene/Trägergeometrie einschließen. Eine Alternative ist
ein expliziter und mitgeführter Rahmenfehler, nicht dessen stilles Weglassen.

### 3.2 Fast singuläre Fälle brauchen eine Fehlerschranke, kein Etikett

Die vorgeschlagenen Vergleichsgeometrien sind mathematisch richtig:

- Fast achsenschneidende Kante: Entfernen des konstanten seitlichen
  Versatzes delta gibt eine paarweise höchstens delta entfernte Kante.
- Fast horizontales Dreieck: Gleiche baryzentrische Punkte unterscheiden
  sich nach Projektion auf die mittlere z-Ebene höchstens um
  delta=(z_max-z_min)/2.
- Flaches Dreieck: Bei einer tatsächlich längsten Kante liegt jeder
  Dreieckspunkt höchstens um die Höhe h von dieser Strecke entfernt.

Der Abstand zu einer festen geschlossenen Oberfläche ist 1-Lipschitz.
Daher gilt für die ersten beiden Fälle bei einer gesicherten
Vergleichsantwort `[L0,U0]`:

```
max(0, L0-delta_upper) <= D <= U0+delta_upper
```

Für die längste Originalkante gilt sogar `L_edge<=D<=U_edge+h_upper`.
Beim Herausrechnen numerischer Rahmen-/Projektionsfehler müssen diese in
delta_upper enthalten sein. „Normalenwinkel unter EPS“ oder
„Dreiecksfläche unter EPS“ allein rechtfertigt keine exakte Vereinfachung.

Zeugen einer Vergleichsgeometrie über deren baryzentrische/lineare Parameter
auf die Originalgeometrie zurückführen und dort erneut auswerten. Sonst
zeigt die Karte einen hohen Wert an einem Punkt, den das Modell nicht hat.

### 3.3 Mögliche Kandidaten und echte Zeugen unterscheiden

Der Plan verlangt das, enthält aber noch keinen ausführbaren
Mitgliedschaftsvertrag. Nötig ist mindestens:

1. Jeder analytische Kandidat erhält eine einschließende Koordinatenbox
   oder äquivalente Parameterintervalle. Radikand-, Halbebenen- und
   Dreiecksbedingungen werden daran geprüft.
2. Ein Kandidat darf nur entfallen, wenn Nichtexistenz oder Ausschluss
   aus dem Dreieck **bewiesen** ist. Ein Vorzeichenintervall über null
   bedeutet „möglich“, nicht „außerhalb“.
3. Mögliche Kandidaten tragen zur oberen Abstandsschranke bei, auch wenn
   sie noch keinen gültigen Zeugen liefern. Man darf bei einem offenen
   Mittelkreiskandidaten beispielsweise F_min=0 konservativ zulassen.
4. Untere Schranken stammen nur von tatsächlichen Punkten im Original-T.
   Ein numerisch projizierter Punkt mit Abstand unter EPS ist dafür kein
   Ersatz. Am Punktdreieck `(11,0,0)` auf einem Torus R=10/r=1 ist D=0;
   bereits `nextafter(11,+inf)` als angeblicher Zeuge liefert fälschlich
   einen positiven Abstand von `1.7763568394002505e-15` mm.

Die kleinste klare Zeugenrepräsentation ist Dreieckindex plus zulässige
baryzentrische Parameter. Ihre exakte reelle Kombination der Original-
float-Ecken bezeichnet den Punkt. Seine numerisch ausgegebenen Koordinaten
werden nur als Annäherung daran behandelt; der Punktabstand wird über die
einschließende Rechnung dieser Kombination begrenzt. Auch ein zum Rand
geklemmter Optimiererkandidat ist nur ein neuer zulässiger Probenpunkt,
kein Beweis für das Vorhandensein des analytischen Extremums.

Für Ausschlussprüfungen genügen die drei orientierten Dreieckshalbräume,
etwa `dot(cross(edge, p-v_i), triangle_normal)>=0`, mit nach außen
gerechneten Vorzeichen. Ist der Normalen-/Flächenbeweis unklar, greift der
Höhenvergleich oder die globale Schranke; keine fast singuläre 2x2-Division
mit nachträglichem epsilon-Clamping.

### 3.4 Monotone Intervalle müssen numerisch wirklich abgedeckt bleiben

Die Nullstellensuche allein zertifiziert kein Extremum. Insbesondere
`rho_c²-w` nahe null, ein fast doppelter Wendepunkt und unsichere
Vorzeichen von F' an einem Teilintervallrand dürfen nicht dazu führen,
dass das Intervall ungeprüft entfällt.

Für eine glatte Kante mit sicher positiver unterer Radiusgrenze ist die
Sehnenschranke des Plans gültig:

```
|F(u)-L_sehne(u)| <= M_F*ell²/8
M_F >= sup |2*D_e - 2*R*Delta/rho³|
```

Für den Kegel analog `M_H>=sup(c*Delta/rho³)`. Alle Größen und Endwerte
benötigen gerichtete Schranken. Bei `rho_lower=0` gibt es keine endliche
Schranke dieser Form; dann die Vergleichskante oder die direkte
Lipschitz-Schranke verwenden, nicht den Nenner auf EPS anheben.

Ein `scipy.optimize.brentq` darf einen Kandidaten oder eine engere
Einklammerung vorschlagen. Seine skalare Rückgabe wird erst durch den
eigenen Intervallnachweis zur Schranke. Eine kompakte Bisektion im
vorhandenen NumPy-/Python-Umfang genügt; freie SLSQP-/Least-Squares-Suche
oder Quartikwurzeln sind hierfür nicht nötig.

## 4. Kleinster praktisch geschlossener Ablauf

### Unverlierbare Ausgangsschranke

Für jeden sicher im Originaldreieck liegenden Probenpunkt w gilt:

```
L_w <= d(w) <= U_w
D <= U_w + max_i norm(v_i-w)
```

Die letzte Aussage folgt aus Konvexität der Norm und 1-Lipschitz von d.
Also mit gerichteten Operationen initialisieren:

```
L  = max_w L_w
U0 = min_w (U_w + max_i norm(v_i-w)_upper)
```

Drei Ecken reichen als Anfang; der baryzentrische Mittelpunkt ist eine
zusätzliche günstige Probe. Solange Koordinaten darstellbar sind, ist U0
eine endliche sichere Antwort, selbst wenn ein Kandidat numerisch offen
bleibt. Jede spätere bewiesene obere Schranke darf mit U0 minimiert werden.
Bei nicht beherrschbarem Überlauf bleibt der Wert unbekannt statt null.

### Verfeinerung

1. Träger einmal validieren und seine numerischen Konstanten einklammern.
   Originaldreieck und sichere Anfangszeugen auswerten, `[L,U0]` bilden.
2. Vergleichsgeometrien nur verwenden, wenn ihre **gesicherte** Fehlerhülle
   hilfreich ist. Sie dürfen die noch offene Breite nicht verstecken.
3. Analytische Kandidaten des Plans erzeugen. Sicher enthaltene Kandidaten
   verbessern L; mögliche Kandidaten bleiben mit ihrer oberen Hülle erhalten.
4. Die drei Kanten vollständig durch Intervalle über `[0,1]` abdecken.
   Vorhandene geschlossene Extremstellen/Wendepunkte setzen nützliche
   Teilungsstellen. Sie sind eine Beschleunigung, keine Voraussetzung für
   die Gültigkeit der Abdeckung.
5. Offene Kantenintervalle zunächst immer durch den direkten Punktabstand
   begrenzen: Bei Mittelpunkt m und Kantenvektor v gilt
   `U_I=d(m)_upper+norm(v)_upper*ell/2`. Die Sehnen-/Ableitungsschranken
   können dies verschärfen. Nur Intervalle mit `U_I>L+epsilon_mm` weiter
   teilen. Das funktioniert auch ohne entschiedenes Ableitungsvorzeichen.
6. **Kleine bevorzugte Zusammenführung:** Die obere Antwort ist das Maximum
   der vollständigen Kanten-Abstandsschranken und der möglichen Achsen-/
   Innenkandidaten. Für den Kegel gibt es keine zusätzlichen glatten
   Innenkandidaten; für den Torus bleiben die höchstens vier aus Abschnitt 2.
   Auf einem enthaltenen Achsenintervall genügt für D bei beiden Formen
   jeweils das größte D an seinen Enden. Die F_min/F_max-Zerlegung liefert
   den Vollständigkeitsbeweis und optionale engere Schranken, braucht aber
   keine zweite Kandidatenverwaltung. Wer sie zur Schärfung verwendet,
   rechnet sqrt/Radius/Betrag vollständig nach außen; keinen unabhängig
   gerundeten Radius anschließend als exakten r-Wert abziehen.
7. Die globale obere Schranke bleibt das Minimum aller vollständigen
   Beweise. Beenden bei `U-L<=epsilon_mm`, bei fest begrenzten Arbeitsschritten
   oder bei fehlender numerischer Verengung. Letztere beiden Fälle ergeben
   `[L,U]` mit Status „begrenzt“, keine behauptete Zielgenauigkeit.

Ein Maximum der Oberfläche benötigt L aus D-Proben; ein Minimum von F
dagegen eigene untere **Funktionsbereichs**schranken. Diese beiden Bedeutungen
von „lower“ im Code ausdrücklich trennen. Die direkte Lipschitz-Schranke
für d kann nicht als untere Schranke von F_min eingesetzt werden. Für ein
offenes Kantenintervall liefert der Punktwert von q mit seinem geometrischen
Radius stattdessen `q_min>=max(0,q(m)_lower-radius_upper)` und entsprechend
`q_max<=q(m)_upper+radius_upper`; Quadrieren gibt gültige F-Grenzen.

Das Arbeitsbudget zählt tatsächlich ausgewertete Intervalle/Kandidaten und
deren Warteschlange, nicht Sekunden. Abbruch vor/nach den kleinen Schritten;
`OperationCancelled` wird durchgereicht. Keine zweite globale Cache- oder
Fitverwaltung, kein vollständiges `Patches × Dreiecke`-Array. Numerischer
Puffer und Abbruchlogik gehören gemeinsam zum vorgesehenen Kartenrechner.

Das bedeutet wenige private Zahlenhelfer im Kartenrechner, **keine neue
generische Intervallbibliothek**. Ein Paar untere/obere float-Grenzen, die
feste Innenkandidatenliste und eine begrenzte Liste offener Kantenintervalle
genügen. Kein Register, kein Solver-Framework und keine neuen semantischen IDs.

Die vorgeschlagenen `AnalysisMap`-Felder passen dazu: intern pro bekannter
Facette `[L_i,U_i]`, nach außen `values[i]=U_i`,
`maximum_interval=(max_i L_i,max_i U_i)` und
`numerical_error=max_i(U_i-L_i)`. Nur den Zeugen des größten L_i mitsamt
`witness_face`, angenähertem `witness_point` und nach unten begrenztem
`witness_distance` behalten; keine zusätzliche vollständige untere Reihe
speichern. Die Obergrenze wird am Zeugen nicht als erreicht ausgegeben.
Bei unbekannten Facetten betrifft dieses Intervall ausdrücklich nur die
**bekannte Abdeckung**, nicht das Maximum der gesamten Körperoberfläche.

## 5. Enger Prüfumfang vor Implementierungsabnahme

Zusätzlich zu den sechs analytischen Fällen des Ausgangsplans:

- Kegel direkt vor/auf/hinter t=0; negative z-Werte auf der Achse;
  beide gerichteten Achsen nach Spiegelung. Doppelnappenformel muss am
  dokumentierten Gegenfall scheitern.
- Kegelkante mit Delta=0, danach mit immer kleinerem positivem Abstand zur
  Achse; Kantenkandidat nahe 0/1 und `k²` von beiden Seiten nahe A.
- Toruskante mit drei stationären Punkten; fast verschmolzene Wendepunkte,
  F'-Nullstelle genau am Wendepunkt und knapp auf beiden Seiten davon.
- Torusebene exakt horizontal sowie stetig kleine Neigungen; exakt
  vertikale Ebene durch/neben der Achse und kleine nichtnull b-Werte.
- Mittelkreis tangiert die Dreiecksebene oder trifft knapp innerhalb,
  auf und außerhalb einer Dreieckskante. Ein möglicher Kandidat darf U
  erhöhen, niemals ungeprüft L. Einzelne Überschreitungen um ein ULP zählen.
- Punktdreieck, kollineare Ecken, sehr flaches Dreieck und ungleich große
  Kanten; vorhandenes Original mit der Vergleichsgeometrie samt Restbreite
  prüfen. Unterteilung darf das globale Maximum nicht verändern.
- Große Welttranslation und schräger Achsvektor, Radius-/Koordinatenskalen,
  bei denen die erreichbare float-Breite größer als epsilon_mm wird.
  Die Ausgabe meldet dann ihre tatsächliche Breite.
- Künstlich kleines Arbeitspaket und Abbruch mitten in einer Kante:
  entweder weiterhin gültiges begrenztes Intervall oder vollständiger
  Abbruch; keine vorherige Teilkarte im Cache.

Prüfkriterium ist `L<=D_soll<=U`, nicht nur „ein Optimierer fand nichts
Größeres“. Ein Intervall einer früheren Auflösung muss den späteren
eingegrenzten Wert weiterhin umfassen; Verfeinerung soll L nicht verkleinern
und U nicht vergrößern. Die bekannten analytischen Sollwerte sind von der
Intervalleinpassung unabhängig. Keine Laufzeitschwelle in diesen Tests.

## 6. Ausgeführte arithmetische Gegenprüfung

Eine Python-Standardeingabe mit `math` und für den Kegelfall
80-stelligem `decimal`, Prozessausgang **0**, lieferte:

- Kegel alpha=45°, rho=1, z=-4: gerichteter Abstand
  `sqrt(17)=4.123105625617660549821409855974…`; branchfreie Formel stimmt
  innerhalb `1e-75`. Falsche Doppelnappenformel: `3.535533905932737622…`.
- Torus R=10, Kante x=-12…12/y=3/z=2: F an den drei stationären Stellen
  `4,53,4` mm².
- Vertikales Torusdreieck x=12: baryzentrischer Zeuge `(1/4,1/4,1/2)` liegt
  bei `(12,0,0)` und liefert das innere Minimum F=4 mm².
- Die beiden numerischen Gegenbeispiele oben reproduzierten den Verlust
  durch eine einzige abschließende `nextafter`-Hülle und den ungültigen
  Zeugen außerhalb eines Punktdreiecks.

Dies prüft die ergänzte Algebra und die konkreten Fallstricke. Es ist weder
eine implementierte Intervallzertifizierung noch ein bestandener P1.6-
Produktlauf. Es wurde keine neue Abhängigkeit eingeführt. Ein allgemeiner
Intervallrechner ist in den untersuchten bestehenden Wahrnehmungs-/Geometrie-
Helfern nicht vorhanden; `geom.mesh_ops.deviation` misst Eckpunktabstände
zwischen Netzen und ist für diesen Beweisvertrag kein Ersatz.
