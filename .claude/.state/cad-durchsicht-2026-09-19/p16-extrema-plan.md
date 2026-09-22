# P1.6 — Begrenzte Facettenextrema für Kegel und Ringtorus

Mathematische Vorbereitung, 20.09.2026. Nur diese Plandatei und eigene
Temp-Sonden; keine Änderung am eingefrorenen Produkt-/Testpaket. Ergänzt
`p16-deviation-plan.md`. Alle folgenden Formeln lesen den vorhandenen Träger.

## Ergebnis und Rechenvertrag

Eine Unterteilung der gesamten Dreiecksfläche ist nicht erforderlich:

- **Kegel:** Außenmaximum an den drei Ecken; Innenmaximum an drei Kanten
  oder auf dem Schnitt des Dreiecks mit der Achse. Kantenextrema geschlossen
  lösbar, ersatzweise eine monotone Nullstelleneinklammerung.
- **Ringtorus:** Abstand zum Mittelkreis minimieren/maximieren. Drei Kanten,
  Achsenschnitt und höchstens vier analytische innere Kandidaten genügen.
  Je Kante höchstens drei stationäre Punkte; alle lassen sich ohne
  mehrdeutige freie Optimierung einklammern.

Ausgabe bleibt `D = max_{p in T} dist(p,S)` in mm für das **ausgefüllte**
Originaldreieck. Numerische Ausgabe ist ein belegtes Intervall `[L,U]` mit
`0 <= L <= D <= U`, einem gültigen Zeugenpunkt im Dreieck und erreichter
Breite `U-L`. Die Zielbreite `epsilon_mm` betrifft ausschließlich diese
Rechnung, keine Nennmaß- oder Fertigungstoleranz. Bei Budgetende bleibt das
Intervall offen ausgewiesen; Nutzerabbruch liefert kein Ergebnis.

Im lokalen Trägerrahmen ist die Achse +Z. `p=(x,y,z)`, `rho=hypot(x,y)`.
Beim Kegel liegt der Ursprung an der Spitze, beim Torus im Zentrum. Rahmen
und Parameter stammen aus der bestehenden erkannten Lösung. Geometrie,
Orientierung und Parameter werden nicht erneut eingepasst.

## 1. Kegel: nur Ecken, Kanten und Achse

Halbwinkel `0 < alpha < pi/2`, `s=sin(alpha)`, `c=cos(alpha)`:

```
H(p) = s*z - c*rho
t(p) = s*rho + c*z
d_surface(p) = abs(H(p))   falls t(p) >= 0
             = norm(p)    sonst
```

Der zweite Zweig ist die Spitze als nächster Punkt. Er verhindert den
falschen Abstand zu einer zweiten, hinter der Spitze liegenden Nappe.

Der ausgefüllte Vorwärtskegel `K={H>=0}` ist konvex. Sein Außenabstand
`d_K` ist innerhalb null und außerhalb `d_surface`. Deshalb gilt:

```
D = max(max(d_K(v0), d_K(v1), d_K(v2)), max_{p in T} H(p), 0)
```

Das Außenmaximum liegt wegen der Konvexität des Abstands an einer Ecke.
`H` ist konkav. Für sein Maximum genügen Kanten und Achse: Die
Dreiecksebene schneidet die Meridianebene durch jeden achsfernen Punkt in
einer Geraden. Auf dieser ist `H` bis zum Achsenknick affin. Ein inneres
Maximum setzt sich daher mit gleichem Wert bis zum Rand oder zur Achse fort.
Es kann kein ausschließlich innen liegender weiterer Höchstwert fehlen.

### Kantenmaximum von H

Kante `p(u)=p0+u*v`, `0<=u<=1`; Index `perp` bezeichnet XY:

```
A = dot(v_perp,v_perp)
B = dot(p0_perp,v_perp)
Delta = cross2(p0_perp,v_perp)**2
u0 = -B/A
w = Delta/A
rho(u)**2 = A*(u-u0)**2 + w
k = v_z*tan(alpha)
```

Immer beide Endpunkte auswerten. Für `A=0` ist `H` affin. Für `Delta=0`
ist es stückweise affin: zusätzlich `u0` auswerten, falls innerhalb der
Kante. Für `Delta>0` existiert ein innerer stationärer Kandidat nur bei
`k*k<A`:

```
u_star = u0 + k*sqrt(w / (A*(A-k*k)))
```

Nur Kandidaten in `[0,1]` übernehmen. `H' = s*v_z-c*(A*u+B)/rho` ist
monoton fallend; unklarer Grenzfall `k*k≈A` lässt sich daher auf derselben
Kante einklammern, ohne eine instabile große Division zu erzwingen.

Achse gegen das Dreieck schneiden: ein Punkt oder eine Strecke. Auf der
Achse ist `H=s*z`; nur das größte enthaltene z ist erforderlich. Bei
entartetem Dreieck genügen seine längste Strecke beziehungsweise sein Punkt.

## 2. Ringtorus: zuerst Abstand zum Mittelkreis

Großer Radius `R`, Rohrradius `r`, ausschließlich `R>r>0`:

```
F(p) = (rho-R)**2 + z*z          # Quadrat des Abstands zum Mittelkreis
q(p) = sqrt(F(p))
d_surface(p) = abs(q(p)-r)
D = max(abs(sqrt(F_min)-r), abs(sqrt(F_max)-r))
```

Die Rohrradius-Umrechnung erfolgt erst am Ende. Insbesondere ist `R` nicht
der Außenradius. Die stabile erste Formel vermeidet die unnötige Auslöschung
in `dot(p,p)+R*R-2*R*rho` nahe dem Mittelkreis.

### Kanten: höchstens drei stationäre Punkte vollständig finden

Für dieselbe Kantenparametrisierung zusätzlich `D_e=dot(v,v)` und
`E=dot(p0,v)`:

```
F'(u)  = 2*(D_e*u+E) - 2*R*(A*u+B)/rho(u)
F''(u) = 2*D_e - 2*R*Delta/rho(u)**3
```

Für `D_e=0` ist die Kante ein Punkt. Für `A=0` ist `F` quadratisch.
Für `Delta=0` am möglichen Achsendurchgang `u0` teilen: auf beiden Seiten
ist `rho=sqrt(A)*abs(u-u0)` und `F` jeweils quadratisch. Endpunkte,
Achsenknick und enthaltene Scheitel liefern die exakten Kandidaten.

Bei `Delta>0` bleibt `rho>0`; die Wendepunkte sind explizit:

```
rho_c = cbrt(R*Delta/D_e)
u_turn = u0 ± sqrt((rho_c*rho_c-w)/A)   # nur falls Radikand >= 0
```

Die enthaltenen Wendepunkte teilen `[0,1]` in höchstens drei Intervalle.
Auf jedem ist `F'` monoton. Alle Grenzpunkte auswerten; bei wechselndem
Vorzeichen genau eine Nullstelle einklammern. Nullstellen an Grenzpunkten
mitnehmen. Ein doppelter stationärer Punkt an einem Wendepunkt geht damit
nicht verloren. Es ist weder eine einzige lokale Minimumsuche noch ein
ungeprüfter Satz komplexer Quartikwurzeln nötig.

### Innere Kandidaten und Achse

Für eine nicht horizontale Dreiecksebene den XY-Rahmen so drehen, dass ihr
normierter Normalenvektor `n=(a,0,b)` lautet, `a>0`, `a*a+b*b=1`.
Die Ebene heißt `a*x+b*z=h`. Zwei Kandidaten liegen in der Meridianebene:

```
j_sigma = h-sigma*a*R
p_sigma = (sigma*R+a*j_sigma, 0, b*j_sigma)    sigma in {-1,+1}
```

Nur bei `sigma*p_sigma.x>0` und tatsächlicher Lage im Dreieck zulässig;
`F(p_sigma)=j_sigma*j_sigma`. Dazu kommen die höchstens zwei Schnittpunkte
der Ebene mit dem Mittelkreis:

```
p_ring = (h/a, ±sqrt(R*R-(h/a)**2), 0)        F=0
```

Wieder nur reelle und im Dreieck liegende Punkte übernehmen. Begründung:
Für `rho>0` muss bei einem inneren Extremum `grad(F)` parallel zu n sein.
Die Y-Gleichung ergibt `y*(1-R/rho)=0`. `y=0` liefert `p_sigma`;
`rho=R` liefert bei `a>0` den Mittelkreis mit `z=0`. Damit sind die glatten
Innenextrema vollständig. Innere glatte **Maxima** wären sogar entbehrlich:
In jeder Meridian-Schnittgeraden ist F streng quadratisch konvex.

Die Achse ist nicht glatt und bleibt ein eigener Kandidat: bei `b!=0`
Punkt `(0,0,h/b)`, falls im Dreieck. Liegt die gesamte Achse in der Ebene,
ihren Schnitt mit dem Dreieck als z-Intervall behandeln: Endpunkte und
enthaltenes `z=0`; dort `F=R*R+z*z`. Geometrische Schnittrechnung statt
Division verwenden, wenn b numerisch nicht sicher von null trennbar ist.

**Horizontale Ebene:** `z=z0` konstant. Das projizierte ausgefüllte Dreieck
liefert das Radiusintervall `[rho_min,rho_max]`: Abstand des Ursprungs zum
Dreieck und größter Eckradius, einschließlich entarteter Projektionen.
Dann direkt:

```
F_min = distance(R, [rho_min,rho_max])**2 + z0*z0
F_max = max((rho_min-R)**2,(rho_max-R)**2) + z0*z0
```

Dies umfasst eine ganze stationäre Kreislinie, ohne einzelne willkürliche
Kreispunkte als vermeintlich vollständige Kandidaten auszuwählen.

## 3. Enge Schranken, Numerik und Ende der Rechnung

Die obige Kandidatenmenge ist in reeller Arithmetik vollständig. Ein bloßer
float-Wert einer Nullstellensuche ist trotzdem noch kein zertifiziertes
Intervall. Für die spätere Umsetzung:

1. Eingaben, Rahmenrechnung und Kandidaten mit nach außen gerundeten
   Intervallen behandeln; gerichtete Grundoperationen/`nextafter` benötigen
   keine neue Abhängigkeit. Kubikwurzelgrenzen durch monotones Kubieren
   überprüfen. Auch `sin/cos(alpha)` brauchen validierte Grenzen; eine
   einzelne libm-Ausgabe wird nicht ohne Fehlerhülle „exakt“ genannt.
2. Für ein verbliebenes Kantenintervall I der Länge ell und
   `M>=max_I abs(F'')` begrenzt die Sehne L durch seine Endwerte F:
   `abs(F-L)<=M*ell*ell/8`. Mit bekannten Vorzeichen von F'' genügt die
   entsprechende einseitige Schranke. `rho_min/rho_max` auf I folgen
   direkt aus dem quadratischen Radiusausdruck. Die Lücke schrumpft somit
   quadratisch, ohne eine ganze Dreiecksfläche zu unterteilen.
3. `Delta` über das Kreuzprodukt berechnen, nicht durch Subtraktion fast
   gleicher `A*C-B*B`. Für fast achsenschneidende Kanten ist die glatte
   Krümmungsschranke ungünstig. Ihre seitliche Entfernung von der Achse ist
   `delta=sqrt(w)`: die mathematische Vergleichskante mit diesem seitlichen
   Versatz null ist stückweise quadratisch exakt lösbar. Die Originalkante
   liegt punktweise höchstens delta entfernt. Deshalb weicht ihr Maximum
   des **Abstands** höchstens delta ab. Für `delta` innerhalb des aktiven
   Fehlerbudgets ist das eine enge direkte Schranke, kein Jitter und kein
   Austausch der gespeicherten Geometrie.
4. Ähnlich bei fast horizontalen Dreiecken: Projektion auf die mittlere
   z-Ebene hat punktweise Versatz höchstens `(z_max-z_min)/2`. Das direkt
   lösbare horizontale Problem begrenzt D um genau diese Distanz. Ein
   fast entartetes Dreieck liegt höchstens seine Höhe von seiner längsten
   Kante entfernt: `D_edge <= D_triangle <= D_edge+height`. Diese Schranken
   entscheiden anhand der verlangten Rechenbreite; keine grobe
   Winkel-/Entartungstoleranz wird als exakte Gleichheit ausgegeben.
5. Unsichere Mitgliedschaft eines analytischen Kandidaten im Dreieck nicht
   still verwerfen. Bis zur Auflösung konservativ begrenzen. Untere
   Schranken/Zeugen nur aus sicher enthaltenen Punkten; vorgeschlagene
   Optimiererpunkte mit leicht verletzten Nebenbedingungen sind keine Zeugen.
6. Beim Torus aus allen Teilintervallen `F_lower<=F_min` und
   `F_max<=F_upper` sammeln. Dann
   `U=max(abs(sqrt(max(0,F_lower))-r),abs(sqrt(max(0,F_upper))-r))`.
   Aus gültigen ausgewerteten Punkten folgt L. Beim Kegel die entsprechenden
   Außen-/H-Schranken maximieren. Rundungsfehler jeweils einschließen.
7. Nur Intervalle verfeinern, deren obere Abstandsschranke größer als
   `L+epsilon_mm` bleibt. Ende bei `U-L<=epsilon_mm`. Vor/zwischen/nach
   Kantenstücken und Intervallschritten Abbruch prüfen. Wenn maschinelle
   Auflösung oder ausdrücklich begrenzte Arbeit keine weitere Verengung
   zulässt, das erreichte Intervall als begrenzt ausweisen; keine Endlossuche
   und kein stiller Nullwert. Keine Teilkarte nach Nutzerabbruch cachen.

Die Fehlerhülle gehört in ein eigenes korrekt benanntes Ergebnisfeld;
`AnalysisMap.resolution` bedeutet weiterhin Rasterweite. Der konservative
obere Skalar ist nur mit dieser Bedeutung/Spanne anzeigbar. Ein echter
Zeugenpunkt liefert einen belegten hohen Wert, bei endlichem Intervall
nicht zwingend den mathematisch exakten Ort des Maximums.

## 4. Kleine unabhängige Gegenfälle und Sondenbefund

| Fall | Analytisches Soll |
|---|---|
| Kegel alpha=45°, Dreieck in z=10, gleichseitige Ecken bei rho=2 um die Achse | Innenmaximum genau auf der Achse: `10/sqrt(2)` mm; Eckproben reichen nicht. |
| Kegel alpha=45°, Kante x=-3…3, y=2, z=5; dritter Dreieckspunkt (0,3,5) | Größte Innentiefe in der Kantenmitte: `3/sqrt(2)` mm. |
| Kegel alpha=45°, Ecken (0,0,-4), (1,0,-4), (0,1,-4) | Hinter der Spitze gilt `sqrt(17)` mm; die Doppelkegelformel wäre falsch. |
| Torus R=10, Kante x=-12…12, y=3, z=2 | Drei stationäre Stellen x=`-sqrt(91),0,+sqrt(91)`; F=`4,53,4` mm². Endwerte nur etwa 9,613662 mm². Eine einzige lokale Minimumsuche verfehlt das Innenmaximum der Kante. |
| Torus R=10, gleichseitiges Dreieck in z=2 mit allen Eckradien 10 | `F_min=4`, `F_max=104` mm²; Höchstwert auf der Achse im Dreiecksinneren. |
| Torus R=10, Dreieck in x=12 mit Ecken (12,-5,-5), (12,5,-5), (12,0,5) | Inneres Minimum bei (12,0,0), F=4 mm²; Kanten allein reichen für F_min nicht. |

Eigene mathematische Sonde in
`C:/Users/rober/AppData/Local/Temp/solidon-p16-extrema-kdejf9qa/`:
48 Dreiecke, gespeicherter Startwert `16062026`, Rastergegenprobe und
unabhängige beschränkte SLSQP-Suchen. Die analytischen Kandidaten hielten
alle geprüften Raster-/Optimiererwerte ein (`probe-final.txt`, Exit 0).
Die Kegelmaxima stimmten in diesen Fällen bis etwa 3,6e-15 mm überein.

Der erste Sondenlauf (`probe.txt`, Exit 1) enthielt drei Scheinwidersprüche:
SLSQP-Zeugen lagen geringfügig außerhalb des Dreiecks. Die Sonde projiziert
seither deren baryzentrische Koordinaten auf den zulässigen Bereich. Außerdem
verfehlte SLSQP in Fall 29 ein echtes Kantenmaximum nahe der Achse:
F=265,371826912 mm² am enthaltenen Punkt
(-1,040940576; -1,465436215; 14,074482889), gegenüber 260,344394862 mm²
aus der freien Vergleichssuche. `probe-locations-final.txt` enthält diesen
Zeugen und die separate Achsengegenprobe F=104 mm². Das bestätigt, warum die
Kandidatenvollständigkeit aus der Herleitung kommen muss.

Die Temp-Sonde verwendet gewöhnliche floats und ist **kein Beweis bereits
implementierter gerichteter Rundung**. Diese bleibt Bestandteil des späteren
Kernvertrags. Keine Leistungs-/Fensterprüfung oder neue Abhängigkeit; keine
Produkt-/Teständerung und kein Commit.
