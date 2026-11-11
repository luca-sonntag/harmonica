# 04 – Algorithmik & Übersetzungs-Pipeline

Dieses Dokument beschreibt, wie die musiktheoretischen und physikalischen Eigenschaften der Steirischen Harmonika in konkrete Algorithmen für **Audio-Filterung**, **automatische Transposition** und **optimale Griffschrift-Generierung (Viterbi-Algorithmus)** überführt werden.

---

## 1. Akustische Besonderheiten bei der Audio-Transkription (DSP & ML)

Wenn ein KI-Modell (z. B. *Basic Pitch*, *MT3* oder *Klangio*) eine Audiodatei einer Steirischen Harmonika in MIDI-Noten übersetzt, treten drei instrumentenspezifische Störeffekte auf, die ein nachgeschalteter **Domänen-Filter** bereinigen muss:

### A. Schwebung (Tremolo)
* **Physik:** Pro gedrücktem Knopf schwingen im Diskant **2 bis 3 Stimmzungen gleichzeitig**, die absichtlich leicht gegeneinander verstimmt sind (z. B. $440\text{ Hz}$ und $443\text{ Hz}$).
* **Akustischer Effekt:** Durch konstruktive und destruktive Interferenz schwankt die Amplitude mit $f_{\text{Beat}} = |f_1 - f_2| \approx 3\text{ Hz}$ (Schwebung).
* **Fehlerbild der KI:** Das Modell interpretiert jedes Lautstärke-Minimum als Ende der Note und stückelt eine lange Note in viele kurze Sechzehntelnoten derselben Tonhöhe.
* **Algorithmische Gegenmaßnahme (Note Merging):** Aufeinanderfolgende Noten mit identischem `pitch`, deren Pause $\Delta t < 60\text{ ms}$ ist und die keinen scharfen Transienten (Anschlag) aufweisen, werden zu einer einzigen Note verschmolzen.

### B. Helikonbässe & Oberton-Maskierung
* **Physik:** Die tiefen Grundbässe der linken Hand ($f_0 \approx 65\text{–}130\text{ Hz}$) besitzen riesige Schalltrichter (Helikonstimmplatten), die extrem starke Obertöne bei $2 f_0$ (+12 Halbtöne) und $3 f_0$ (+19 Halbtöne) abstrahlen.
* **Fehlerbild der KI:** Das Modell halluziniert die Obertöne des Basses als tiefe Melodienoten der rechten Hand.
* **Algorithmische Gegenmaßnahme (Harmonic Sieve & Split-Point):**
  1. **Frequenz-Trennung:** Töne unterhalb von `MIDI 58` ($b$, $233\text{ Hz}$) gehören physikalisch immer zur linken Hand (Bass/Begleitung), da der tiefste reguläre Diskantton einer `G-C-F-B`-Harmonika bei `MIDI 60` ($c'$) bzw. `62` ($d'$) beginnt.
  2. **Oberton-Filter:** Wenn zum Zeitpunkt $t$ ein tiefer Grundbass $p_{\text{Bass}}$ erkannt wird, werden schwache gleichzeitige Detektionen bei $p_{\text{Bass}} + 12$ und $p_{\text{Bass}} + 19$ als Oberton-Artefakte gedämpft.

### C. Physikalischer Hardware-Constraint-Filter
Eine 4-reihige Harmonika in `G-C-F-B` kann im Diskant überhaupt nur eine feste Teilmenge von MIDI-Tönen erzeugen (und pro Balgrichtung sogar nur ein noch kleineres Set!).
* Jeder von der Audio-KI erkannte Ton $p$, der in der gewählten Harmonika-Stimmung gar nicht in der Lookup-Tabelle existiert, ist **garantiert ein Messfehler** und wird auf den nächstgelegenen gültigen Harmonika-Ton korrigiert oder verworfen.

---

## 2. Automatische Transposition in eine spielbare Harmonika-Tonart

Unsere interne Griffschrift-Engine rechnet immer normiert auf der Referenz-Stimmung **`G-C-F-B`**.
Auf einer `G-C-F-B`-Harmonika lassen sich Stücke nur in vier Dur-Tonarten sinnvoll spielen (entsprechend den 4 Reihen):
1. **G-Dur** (1. Reihe, Grundton `pitch % 12 == 7`)
2. **C-Dur** (2. Reihe – **bevorzugte Hauptreihe!**, Grundton `pitch % 12 == 0`)
3. **F-Dur** (3. Reihe, Grundton `pitch % 12 == 5`)
4. **B-Dur** (4. Reihe, Grundton `pitch % 12 == 10`)

### Algorithmus zur optimalen Transposition ($\Delta p$):
Wenn das Eingabestück z. B. in **D-Dur** oder **A-Dur** vorliegt, testen wir alle sinnvollen Halbtontranspositionen $\Delta p \in [-6 \dots +6]$ und wählen dasjenige $\Delta p$, das:
1. **100 % der Melodietöne** in den gültigen Wertebereich der `G-C-F-B`-Lookup-Tabelle abbildet (vorzugsweise auf Reihe 2 = C-Dur oder Reihe 3 = F-Dur).
2. Die **Tonumfangs-Mitte (Centroid)** der Melodie möglichst nah an den **Gleichton (Knopf 6, `MIDI 79` in Reihe 2 bzw. `MIDI 84` in Reihe 3)** legt, damit das Stück im bequemsten mittleren Bereich des Griffbretts liegt.

---

## 3. Der Griffschrift-Optimierer: Viterbi-Algorithmus auf einem DAG

Nach der Transposition haben wir eine Folge von diskreten Zeitpunkten $t = 1 \dots N$.
Zu jedem Zeitpunkt $t$ erklingt eine Menge gleichzeitiger Diskant-Töne $P_t = \{p_1, p_2, \dots, p_m\}$ (meist $m=1$ für Einzelton, $m=2$ für Terz/Sext-Zweiklang, $m=3$ für Dreiklang) sowie optional ein erkannter Bass/Akkord $H_t$.

### Schritt 1: Kandidaten-Generierung pro Zeitpunkt $t$ (Hard Constraints)
Für jeden Einzelton $p_i \in P_t$ liefert unsere Hardware-Lookup-Tabelle alle Knöpfe $(r, b, d)$, die diesen Ton erzeugen.
Für den Gesamtgriff zum Zeitpunkt $t$ bilden wir das kartesische Produkt und filtern nach **harten physikalischen Regeln**:

1. **Balg-Konsistenz:** Alle gleichzeitig gedrückten Knöpfe müssen dieselbe Balgrichtung $d \in \{\text{DRUCK}, \text{ZUG}\}$ haben:
   $$d_1 = d_2 = \dots = d_m$$
2. **Keine Doppelbelegung:** Zwei Töne eines Akkords dürfen nicht denselben physischen Knopf $(r, b)$ belegen.
3. **Menschliche Handspanne:** Der maximale Knopf-Abstand innerhalb eines Griffs darf 5 Knöpfe nicht überschreiten:
   $$\max_{i,j} |b_i - b_j| \le 5$$

Das Ergebnis ist für jeden Zeitpunkt $t$ eine kleine Liste gültiger **Griff-Kandidaten (Zustände)** $S_t^{(1)}, S_t^{(2)}, \dots, S_t^{(K)}$ (typischerweise $K \in \{2 \dots 8\}$).

---

### Schritt 2: Kostenfunktion (Soft Constraints / Ergonomie-Heuristik)

Wir modellieren die Zustände über die Zeit $t = 1 \dots N$ als **gerichteten azyklischen Graphen (Trellis-DAG)** und definieren zwei Kostenfunktionen:

#### A. Knotenkosten `nodeCost(S_t)` (Wie ergonomisch ist der Griff selbst?)
* **Harmonie-/Bass-Übereinstimmung:**
  * Widerspricht die Balgrichtung $d$ von $S_t$ der erkannten Bass-Harmonie $H_t$ (z. B. Tonika C-Dur auf `ZUG` statt `DRUCK`)? $\rightarrow$ **`+50.0` Strafpunkte**.
* **Reihen-Reinheit bei Mehrklängen ($m \ge 2$):**
  * Alle Knöpfe des Zweiklangs/Dreiklangs liegen in **derselben Reihe**? $\rightarrow$ **`+0.0` Strafpunkte** (Idealfall auf der Steirischen!).
  * Knöpfe liegen auf **benachbarten Reihen** ($\Delta r = 1$)? $\rightarrow$ **`+4.0` Strafpunkte**.
  * Knöpfe überspringen Reihen ($\Delta r \ge 2$)? $\rightarrow$ **`+15.0` Strafpunkte**.
* **Präferenz für Hauptreihen:**
  * Nutzung von Reihe 2 oder 3: **`+0.0`**.
  * Nutzung von Reihe 1 oder 4 (Randreihen): **`+1.5`**.
  * Nutzung von Halbton-/Sondertasten (Knopf 1 & 2): **`+8.0`** (nur nutzen, wenn diatonisch nicht anders möglich).

#### B. Übergangskosten `edgeCost(S_{t-1}, S_t)` (Wie flüssig ist der Wechsel?)
* **Balgwechsel-Strafe (`S_{t-1}.dir != S_t.dir`):**
  * Findet der Balgwechsel **mitten in einer schnellen Achtel-/Sechzehntel-Gruppe** statt? $\rightarrow$ **`+35.0` Strafpunkte** (verhindert nervöses „Hecheln“ des Balgs).
  * Findet der Balgwechsel **auf einer Taktgrenze (Beat 1)** oder nach einer Pause statt? $\rightarrow$ **`+3.0` Strafpunkte** (natürlicher Wendepunkt).
* **Hand-Sprungdistanz:**
  * Abstand des mittleren Knopf-Index $\Delta b = |\bar{b}_t - \bar{b}_{t-1}|$:
    $$\text{jumpCost} = 1.2 \cdot \max(0, \Delta b - 1)^2$$
    *(Kleine Schritte zu Nachbarknöpfen sind kostenlos; weite Sprünge über das Griffbrett werden quadratisch bestraft).*
* **Reihen-Kontinuität:**
  * Wechsel der Reihe zwischen $t-1$ und $t$: **`+2.5` Strafpunkte** (hält Melodieläufe in derselben Reihe, solange es sinnvoll ist).

---

### Schritt 3: Globales Optimum via Dynamischer Programmierung (Viterbi)

Anstatt gierig (Greedy) von Note zu Note zu entscheiden – was oft nach 3 Noten in einer Sackgasse am Rand des Griffbretts endet –, berechnet der **Viterbi-Algorithmus** den Pfad mit der minimalen Gesamtkostensumme über das gesamte Musikstück (oder pro musikalischer Phrase):

$$DP[t][k] = \text{nodeCost}(S_t^{(k)}) + \min_{j} \left( DP[t-1][j] + \text{edgeCost}(S_{t-1}^{(j)}, S_t^{(k)}) \right)$$

```kotlin
// Komplexität: O(N * K^2) mit N ≈ 300 Noten, K ≈ 6 Kandidaten -> ~10.000 Operationen (< 1 ms)
```

Durch Backtracking entlang der gespeicherten `prevIndex[t][k]`-Zeiger erhalten wir die global optimale Griffschrift-Spur.

---

## 4. Interaktives User-Override (Constraint Injection)

Ein riesiger Vorteil des Viterbi-Ansatzes für die Android-App:
Wenn der Nutzer in der App-Vorschau auf **Takt 4** tippt und sagt *„Spiele diesen Takt lieber auf `DRUCK` statt auf `ZUG`“*, müssen wir keinen einzigen neuen Algorithmus schreiben:
1. Wir setzen für alle Zeitpunkte $t \in \text{Takt 4}$ einen Filter `candidate.dir == DRUCK`.
2. Wir lassen den Viterbi-Algorithmus in **< 1 Millisekunde** neu über das Stück laufen.
3. **Automatischer Nachbarschafts-Ausgleich:** Der Algorithmus passt nicht nur Takt 4 an, sondern wählt am Ende von Takt 3 und am Anfang von Takt 5 automatisch die ergonomisch besten Anschluss-Griffe für den geänderten Balgzustand!

---

## 5. Dual-Track MusicXML & PDF-Generierung

Am Ende der Pipeline stehen zwei synchronisierte Listen über dieselben Takte:
1. **`Part 1 (Normalnoten)`:** Enthält die transponierten echten Töne (`<pitch>` entspricht dem klingenden Ton, `<fifths>` entspricht der echten Tonart, z. B. C-Dur oder F-Dur).
2. **`Part 2 (Griffschrift)`:** Enthält exakt dieselben Rhythmen und Taktstriche, aber:
   * `<fifths>0</fifths>` (keine Generalvorzeichen).
   * `<pitch>` berechnet über die Formel $\text{staffStep}(\text{row}, \text{button}) = (\text{row} - 2) + 2 \cdot (\text{button} - 6)$ (siehe [03-griffschrift-spezifikation.md](file:///c:/Users/lucas/source/repos/harmonica/docs/03-griffschrift-spezifikation.md)).
   * `<notehead>x</notehead>` für `row in {3, 4}`.
   * Durchgehender Druckbalken (`<bracket>`) unter allen Takten/Noten mit `direction == DRUCK`.
   * Bass-Buchstaben (`A/a`, `B/b`, `C/c`, `D/d`) als `<lyric>` oder `<words>` unterhalb des Systems.

Beide `<part>`-Spuren werden in einer einzigen MusicXML-Datei an **Verovio** übergeben, das daraus seitenweise Vektor-SVGs rendert, die direkt in ein druckfertiges Android-`PdfDocument` gezeichnet werden.
