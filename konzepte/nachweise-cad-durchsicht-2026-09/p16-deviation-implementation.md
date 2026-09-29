# P1.6 – numerischer Kern: eingefrorener Stand und Reviewauftrag

Der eingefrorene Kern besteht aus `app/core/geom/deviation.py`,
`tests/test_surface_deviation.py` und dem zusammenhängenden Absatz über
`deviation.deviation_bounds` in `app/core/geom/CLAUDE.md`. Andere Absätze der
Karte gehören zur parallelen Arbeit. Keine Änderung an `units.py`,
`measure.py`, `evaluate.py`, Export, Oberfläche oder Katalogen durch dieses
Paket. Kein Commit und kein Push durch den Unteragenten.

## Vertrag und Reichweite

```python
@dataclass(frozen=True, slots=True)
class FacetDeviation:
    lower_mm: float
    upper_mm: float
    witness_uv: tuple[float, float]
    converged: bool

def deviation_bounds(
    patch: SurfacePatch,
    triangles: Iterable[Triangle],
    *,
    epsilon_mm: float,
    cancelled: CancelToken | None = None,
) -> Iterator[FacetDeviation | None]: ...
```

Ein Ergebnis je ursprünglichem ausgefülltem Dreieck, in Eingabereihenfolge.
Für den Abstand `d` zum bereits gespeicherten unbeschnittenen Träger gilt
`L <= max_T d <= U`. `epsilon_mm` ist ein numerisches Rechenziel in mm,
keine Fertigungs-, Material- oder Nennmaßunsicherheit. Das Ergebnis behauptet
weder eine neue Einpassung noch den Abstand zu einem beschnittenen B-Rep-Rand.
Die tatsächliche Dreieckszuordnung übernimmt ausschließlich der Aufrufer.

Der Zeuge `(u,v)` bezeichnet die **exakte reelle** Kombination der
ursprünglichen Float-Ecken `(1-u-v)*p0 + u*p1 + v*p2`. `u`, `v` sind endliche
Floats mit exakt rational geprüftem `u>=0`, `v>=0`, `u+v<=1`. Der untere Wert
ist eine untere Abstandsschranke an genau diesem Punkt. Ein gerundeter
Anzeigepunkt ersetzt diesen Vertrag nicht. Obere Kandidaten dürfen auch
numerisch noch nicht sicher im Dreieck liegen; sie liefern dann keinen
unteren Nachweis.

Unterstützt sind Ebene, Zylinder, Kugel, gerichteter einseitiger Kegel mit
`0<half_angle<pi/2` und Ringtorus mit `R>r>0`. Horn- und Spindeltori bleiben
ungültig. `valid_patch` ist der gemeinsame Eingangswächter. Nicht endlich
einschließbare Daten liefern `None`; eine gültige breite Klammer bleibt
bekannt und meldet `converged=False`. Abbruch wird unverändert durchgereicht.

## Arithmetische Beweisbausteine

- Addition, Subtraktion, Multiplikation, Division, Quadrat und alle
  Dot-/Cross-Zwischenschritte rechnen mit nach außen gerichteten Floatgrenzen.
  Es gibt keine abschließende pauschale ULP-Hülle um einen BLAS-Wert.
- `math.sqrt` liefert nur einen Vorschlag. Exaktes Quadrieren mit `Fraction`
  bestätigt jede Wurzelgrenze; höchstens acht auswärts gerichtete Schritte,
  sonst keine behauptete Schranke. Skalierte Normen vermeiden unnötiges
  Quadrieren sehr großer oder sehr kleiner Originalwerte.
- `units.exact_sin/exact_cos` liefern reproduzierbare Zahlen, aber keine
  veröffentlichte Rest-/Rundungsklammer. Deshalb einmal je Kegelträger
  32 feste rationale Reihenschritte; zwei aufeinanderfolgende exakte
  Teilsummen schließen Sinus/Kosinus ein. Für den gespeicherten Winkel fallen
  die Beträge der Folgeterme streng. Rationale Grenzen werden überprüft
  auswärts in Floats umgerechnet. Keine libm-ULP-Annahme.
- Der Achsvektor wird vor der Rechnung durch seine größte Komponente
  skaliert. Mit vollständigen Intervallen gelten danach
  `z=dot(w,axis)/norm(axis)` und
  `q=cross(w,axis)/norm(axis)`, `rho=norm(q)`.
  Ein nur ungefähr orthonormaler Float-Rahmen wird nicht vorausgesetzt.
- Jede Dreiecksrechnung startet mit echten Eckzeugen und `(1/4,1/4)`.
  Aus 1-Lipschitz des Oberflächenabstands und Konvexität der Norm folgt
  `U0=min_w(d(w).hi + max_i norm(v_i-w).hi)`.
  Diese sichere globale Schranke bleibt beim Scheitern einer engeren
  Kandidatenrechnung erhalten. Nur bestätigte obere Schranken verkleinern U.

## Formen und Vollständigkeit der oberen Schranke

**Ebene:** Betrag einer affinen Funktion; das Maximum liegt an einer Ecke.

**Kugel und Zylinder:** Die Norm besitzt ihr Maximum an einer Ecke. Eine
beliebige endliche Richtung liefert über eine gerichtete Stützebene eine
untere Schranke des kleinsten Radius im Dreieck. Kanten- und Innenprojektionen
erzeugen lediglich echte Proben und neue Stützrichtungen; ihre numerische
Optimalität ist keine Voraussetzung für Gültigkeit. Das eingeschlossene
Radiusintervall wird vollständig durch `abs(radius-R)` abgebildet.

**Kegel:** Mit `s=sin(alpha)`, `c=cos(alpha)`, `H=s*z-c*rho`,
`t=s*rho+c*z` gilt der gerichtete Abstand
`sqrt(H²+min(t,0)²)`. Der Abstand zum konvexen Kegelkörper hat sein Maximum
an einer Ecke. Der innere Anteil H ist konkav; für jede nachweislich auf
Norm höchstens eins begrenzte Richtung n liefert
`H <= s*z-c*dot(n,q)` eine globale affine Obergrenze. Daher umfasst
`max(0, Eckabstand_zum_Körper, H_Stützobergrenze)` das ganze Dreieck.
Geschlossene Kantenextremstellen, Achsenschnitt und Untergradientenvorschläge
schärfen die Probe bzw. Stützung; fehlerhafte Optimierungsnähe kann nur die
Breite verschlechtern. Es gibt keine langsame vollständige Flächenunterteilung.

**Ringtorus:** `F=(rho-R)²+z²`, `d=abs(sqrt(F)-r)`.
Ein erstes Radius-/Höhenrechteck umfasst auch fast horizontale Flächen ohne
deren Neigung auf null zu setzen. Für engere Grenzen werden alle drei
Kanten und die vollständigen inneren Kandidatentypen aus dem Extrema-Review
verwendet: zwei Meridianhalbebenen-Kandidaten, höchstens zwei
Mittelkreisschnittpunkte sowie die Achse. Die tatsächliche Halbebenenlage
wird berücksichtigt. Nur gerichtet bewiesene Außenlage entfernt einen
Kandidaten. Unentschiedene Kandidaten bleiben in U enthalten.

Achse, Koplanarität und Dreiecksentartung werden aus den Originalfloats mit
`Fraction` entschieden. Bei enthaltenem Achsenintervall genügen dessen
Endpunkte: Wegen `R>r` ist der Abstand dort konvex in z. Bei exakt
kollinearem Dreieck decken seine drei Kanten die Fläche ab. Ist der
numerische Normalen-/Radialprojektionsnachweis sonst offen, bleiben die
globalen bzw. rechteckigen Schranken gültig; die Kandidatenliste wird nicht
trotzdem als vollständig benutzt.

Jedes Toruskantenintervall besitzt zuerst eine direkte Lipschitzschranke.
Ein bewiesenes Ableitungsvorzeichen begrenzt F durch die Endwerte. Andernfalls
schärft bei `rho_lower>0` die gerichtete Sehnenschranke
`|F-L_sehne| <= M*ell²/8`, mit
`M=2*|edge|²+2*R*Delta/rho_lower³ >= sup |F''|`, vollständig nach oben
gerechnet. `Delta` entsteht über das
Kreuzprodukt, nicht durch auslöschendes `A*C-B²`. Bei `rho_lower=0` wird
kein künstlicher Nenner eingesetzt. Alle Teilintervalle bleiben abgedeckt;
Kinder dürfen die bestätigte Obergrenze ihres Elternintervalls übernehmen.
Die Intervallmitte und der Parameterabstand zu beiden Enden werden
auswärts gerechnet. Die obere Auswertung einer Kante verwendet deren exakte
affine Parameterkombination als Intervall, nicht einen gerundet
zurückgerechneten baryzentrischen Probenpunkt.

## Begrenzung, Abbruch und verbleibende Grenzen

- Insgesamt höchstens **256 ausgewertete Toruskantenintervalle je Aufruf**,
  einschließlich der ersten drei Intervalle pro bearbeitetem Dreieck.
  Ein Kindpaar verbraucht zwei Einheiten. Danach erhalten weitere Dreiecke
  ihre schnellen gültigen Ausgangs-/Rechteckklammern. Kein neuer Topf je
  Dreieck und keine Zeitmessung als Abbruchkriterium.
- Die notwendige anfängliche Arbeit bleibt fest je Eingabedreieck und damit
  linear in deren Zahl. Feste Kandidaten- und rationale Achsenrechnungen
  sind ebenfalls begrenzt je Dreieck. Es gibt keinen vom Eingang unabhängigen
  Gesamtzeitbeweis; der Aufrufer verarbeitet blockweise mit Fortschritt.
- Abbruch wird vor und während Trägervorbereitung, zwischen Proben,
  Kandidaten und Kantenintervallen sowie vor jedem Ergebnis geprüft.
  Ein abgebrochenes Dreieck wird nicht als Teilantwort ausgegeben.
- Extrem schlechte Kondition oder sehr große Weltkoordinaten können eine
  breite endliche Klammer ergeben. Rechenziel nicht erreicht bedeutet
  ausdrücklich nicht Zielgenauigkeit erreicht. Überlauf des schon
  erforderlichen Anfangsnachweises ergibt unbekannt, niemals Null.
- Es wurde kein Zeit-/Leistungsnachweis und keine Fensterprüfung ausgeführt.
  Diese Kernfälle ersetzen keine Release-Abnahme. Die mathematische
  Gegenprüfung des eingefrorenen Codes durch einen zweiten Bearbeiter sowie
  der gemeinsame Karten-/Cache-/UI-Anschluss liegen beim Elternagenten.

## Direkte Belege

Protokollverzeichnis:
`%TEMP%/solidon-deviation-7dd569a2a6fd465d9d44e1a3afab76c0`.

| Protokoll / Prüfung | Direkter Ausgang |
|---|---|
| `red.txt`, API noch nicht vorhanden | Exit 2, Sammlungsfehler; kein geometrischer Gegenbeweis |
| `baseline-red.txt`, gültige bloße Lipschitzbasis | Exit 1, 9 fehlgeschlagen / 10 bestanden; neun zu breite Intervalle |
| `plane-round-cone.txt` | Exit 1, 3 fehlgeschlagen / 16 bestanden; Torus noch offen |
| `five-surfaces-first.txt` | Exit 0, 19 bestanden |
| `adversarial-first.txt` | Exit 1, 1 fehlgeschlagen / 47 bestanden; initiale Kantenarbeit noch nicht mitgezählt |
| `adversarial-second.txt` | Exit 0, 48 bestanden; Zähler korrigiert |
| `rounding-and-limits.txt` | Exit 0, 64 bestanden |
| `affected.txt` | Exit 1, 1159 bestanden / 1 fehlgeschlagen; parallele Organizer→Perceive-Importkante, beim Elternagenten behoben und separat geprüft |
| `final-focused.txt` | Exit 0, 65 bestanden |
| `python -m ruff check .` | Exit 0 |
| `python -m ruff format --check app/core/geom/deviation.py tests/test_surface_deviation.py` | Exit 0 |
| `python -m mypy app/core/geom/deviation.py` | Exit 0 |

Der breite rote Lauf wird nicht nachträglich zum grünen Nachweis umbenannt.
Der Elternagent hat ausdrücklich seine separate Architekturprüfung
übernommen; keine Wiederholung der 1159 Fälle durch diesen Unteragenten.

Die 65 aktuellen Kernfälle enthalten neun unabhängige vollständige
Dreiecksmaxima, Punktdreiecke, alle fünf Träger mit unabhängigem
90-stelligem Decimal-Punktabstand, exakt rational rekonstruierte Zeugen,
deterministische Zufallsdreiecke und rationale Innenpunkte,
große Welttranslation/Achsskalierung, Torusneigungen und Tangentiallagen,
gerichtete Kegellagen und Winkelgrenzen, Unterteilung und monotone
Verfeinerung, Primitive gegen Fraction, nicht exakt darstellbares `1-t`,
begrenzte Gesamtarbeit, ungültige/überlaufende Eingaben und echte Abbrüche
während Vorbereitung und Kantenrechnung. Stichproben sind dabei ergänzende
Gegenfälle; sie ersetzen nicht die obigen Vollständigkeitsargumente.

## Enger unabhängiger Reviewauftrag

1. Gerichtete Primitive, skalierter Rahmen und rationaler Trigrest: keine
   unbewiesene Rundungsannahme in einem oberen oder unteren Beweispfad.
2. Torus: vollständige Kandidatenabdeckung einschließlich Meridianhälften,
   Achse, horizontaler/vertikaler und entarteter Dreieckslage; eine unsichere
   Mitgliedschaft darf nur die Breite vergrößern.
3. Kanten: korrekte Sehnen-/Ableitungsgrenzen und ununterbrochene
   Intervallabdeckung auch nach Rundung und ausgeschöpftem Arbeitszähler.
4. Jeder untere Wert gehört zu seinem **Originaldreieckszeugen**; der
   Kartenanschluss darf U nicht als am Zeugen erreichte Entfernung ausgeben.
5. Unbekannte Abdeckung, verbleibende numerische Breite und Abbruch müssen
   bis Karte/Anzeige/Cache erhalten bleiben. Das ist Anschlussumfang des
   Elternagenten, keine durch diese 65 Fälle behauptete Gesamtfreigabe.

## Vorwärtskorrektur aus unabhängigem Review: Überlauf am Abschluss

`exact_transform_kernel` belegte eine endliche Kugel mit Radius 10 und den
Dreiecksecken `(1.55e308,±0.4e308,0)` sowie `(1.55e308,0,0.4e308)`.
Das mit 400-stelligem Decimal unabhängig bestimmte Maximum ist noch als
Float darstellbar (`1.6007810593582123e308`). Die anfängliche Lipschitzsumme
lief jedoch auf unendlich; die anschließende engere Rechnung blieb
arithmetisch offen. Der bisherige Abschluss publizierte dadurch
`upper_mm=inf`. Dieser konkrete Fehler ist mit einem neuen Kernfall
reproduziert, nicht durch ein verändertes Maß oder eine Toleranz umgangen.

Der Abschluss benutzt jetzt erneut den vorhandenen Intervallwächter `_I`
für beide Grenzen. Nicht endliche oder ungeordnete Grenzen werden damit
vor Ausgabe zu `None`. Die zulässige spätere Verbesserung wäre ein tatsächlich
endlicher geometrischer Nachweis; eine unendliche Zahl bleibt keine bekannte
Antwort. Die Kartenbeschreibung nennt diesen abschließenden Vertrag.

- `review-overflow-red.txt`: direkter Exit 1, 1 fehlgeschlagen / 65 bestanden.
- `review-overflow-green.txt`: direkter Exit 0, **66 bestanden**.
- Ruff, Formatprüfung und reguläres mypy der eigenen Python-Dateien:
  jeweils direkter Exit 0.
- Originalsonde des Reviewers `overflow.py` erneut direkt ausgeführt:
  Exit 0, unabhängiges Maximum weiterhin endlich, Ergebnis jetzt `None`.

Diese Änderung brach ausschließlich das numerische Freeze für den belegten
Abschlussfehler auf. Keine breiten Verbrauchertests, Fensterdateien oder
Leistungsprüfungen wurden dafür wiederholt. Der Reviewer hat den Wächter
und seine unveränderte Originalsonde unabhängig bestätigt: `overflow-after.txt`
im Reviewverzeichnis enthält Exit 0 und `result None`; kein weiterer belegter
Numerikbefund. Der Stand ist erneut eingefroren. SHA-256 von `deviation.py`:
`2E390D567ECCB2562C48F544ED9E6B45D48C09008A21CD2CFCE1E83C4B907059`.
