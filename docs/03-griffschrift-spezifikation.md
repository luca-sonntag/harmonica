# 03 – Griffschrift-Spezifikation (System Max Rosenzopf)

Dieses Dokument spezifiziert die **Griffschrift** (entwickelt 1975 von Max Rosenzopf, heute der De-facto-Standard im gesamten Alpenraum) als formales Kodierungssystem und zeigt, wie man sie verlustfrei in **MusicXML** abbildet.

---

## 1. Grundprinzip: Scancodes im 5-Linien-Gewand

Während die Normalnotation beschreibt, **welcher Ton erklingen soll** (Frequenz / MIDI-Pitch), beschreibt die Griffschrift ausschließlich die **physische Tasten-Koordinate**:

```kotlin
data class GriffEvent(
    val row: Int,              // Knopfreihe: 1, 2, 3 oder 4
    val button: Int,           // Knopf-Index: 1..12 (6 = Gleichton)
    val direction: BellowsDir, // Balgzustand: DRUCK oder ZUG
    val isSemitone: Boolean    // true bei Halbton-/Sondertasten (Knopf 1/2)
)
```

Um kein völlig neues Grafikformat für Musikdruck erfinden zu müssen, nutzt die Griffschrift ein gewöhnliches **5-Linien-Notensystem** als visuelles Raster:
* **X-Achse & Notenhälse/Fähnchen:** Identisch zur Normalnotation (Viertel-, Achtel-, Sechzehntelnoten, Pausen, Taktstriche).
* **Y-Achse (Linien & Zwischenräume):** Codiert **nicht** die Tonhöhe, sondern die **Knopf-Nummer (`button`)** und ob die **Reihe (`row`) gerade oder ungerade** ist!

---

## 2. Die exakte Koordinaten-Formel (Y-Achse & Notenkopf)

### A. Gerade vs. Ungerade Reihen
Das 5-Linien-System teilt die 4 Reihen der Harmonika in zwei Gruppen:
1. **Ungerade Reihen (`Reihe 1` und `Reihe 3`):** Sitzen **immer in den Zwischenräumen** (zwischen den Linien).
2. **Gerade Reihen (`Reihe 2` und `Reihe 4`):** Sitzen **immer direkt auf den Notenlinien** (bzw. auf Hilfslinien).

### B. Äußere vs. Innere Reihen (Notenkopf-Form)
Da sich Reihe 1 & 3 (Zwischenräume) sowie Reihe 2 & 4 (Linien) dieselben Y-Arten teilen, unterscheidet man sie durch die **Form des Notenkopfs**:
1. **Reihe 1 & Reihe 2:** Normaler **runder/ovaler Notenkopf** (`●` bei Viertel/Achtel, `○` bei Halben).
2. **Reihe 3 & Reihe 4:** **Kreuz-Notenkopf** (`×`, in MusicXML: `<notehead>x</notehead>`, bei halben Noten `<notehead>circle-x</notehead>` oder `x` mit Hals).

| Reihe | Y-Position im Notensystem | Notenkopf-Symbol | MusicXML `<notehead>` | Gleichton (Knopf 6) liegt auf... |
| :---: | :--- | :---: | :---: | :--- |
| **1. Reihe** | **Zwischen** den Linien | Rund (`●`) | *(Standard)* | *(kein Gleichton; Knopf 6 = Raum 2–3)* |
| **2. Reihe** | **Auf** den Linien | Rund (`●`) | *(Standard)* | **3. Linie (Mittellinie)** |
| **3. Reihe** | **Zwischen** den Linien | Kreuz (`×`) | `x` | **Zwischenraum 3–4** |
| **4. Reihe** | **Auf** den Linien | Kreuz (`×`) | `x` | **4. Linie** |

---

## 3. Die mathematische Abbildungsformel für den Code

Definiert man die **mittlere (3.) Notenlinie** als Ursprung `staffStep = 0`, dann bewegt sich jeder nächste Knopf innerhalb derselben Reihe (`button + 1`) um **exakt `+2` Stufen** nach oben (von Linie zu Linie bzw. von Zwischenraum zu Zwischenraum).

Damit gilt für **alle 4 Reihen und alle Knöpfe** eine einzige geschlossene lineare Gleichung:

$$\text{staffStep}(\text{row}, \text{button}) = (\text{row} - 2) + 2 \cdot (\text{button} - 6)$$

### Probe an den Orientierungspunkten (Knopf 6 = Gleichton):
* `row = 2, button = 6` $\rightarrow$ $(2 - 2) + 2 \cdot 0 = \mathbf{0}$ (Mittlere / 3. Linie – gerade $\rightarrow$ Linie!)
* `row = 3, button = 6` $\rightarrow$ $(3 - 2) + 2 \cdot 0 = \mathbf{+1}$ (Zwischenraum über 3. Linie – ungerade $\rightarrow$ Raum!)
* `row = 4, button = 6` $\rightarrow$ $(4 - 2) + 2 \cdot 0 = \mathbf{+2}$ (4. Linie – gerade $\rightarrow$ Linie!)
* `row = 1, button = 6` $\rightarrow$ $(1 - 2) + 2 \cdot 0 = \mathbf{-1}$ (Zwischenraum unter 3. Linie – ungerade $\rightarrow$ Raum!)

### Umrechnung von `staffStep` in MusicXML `<pitch>` (Fake-Pitch-Trick)
Damit Standard-Renderer wie **Verovio** oder **OSMD** einen Griffschrift-Notenkopf auf die richtige Linie zeichnen, übergibt man ihnen im Violinschlüssel (`G`-Clef) einfach diejenige Pseudo-Tonhöhe (`<step>` und `<octave>`), die im Violinschlüssel auf dieser Linie liegt:

| `staffStep` | Position im 5-Linien-System | MusicXML `<step>` | MusicXML `<octave>` | Entspricht Knopf in... |
| :---: | :--- | :---: | :---: | :--- |
| `-7` | Raum unter 1. Hilfslinie unten | `B` | `3` | Reihe 1, Knopf 3 |
| `-6` | 1. Hilfslinie unten | `C` | `4` | Reihe 2, Knopf 3 |
| `-5` | Raum unter 1. Linie | `D` | `4` | Reihe 1, Knopf 4 / Reihe 3, Knopf 3 |
| `-4` | **1. Linie (unten)** | `E` | `4` | Reihe 2, Knopf 4 / Reihe 4, Knopf 3 |
| `-3` | **1. Zwischenraum (1–2)** | `F` | `4` | Reihe 1, Knopf 5 / Reihe 3, Knopf 4 |
| `-2` | **2. Linie** | `G` | `4` | Reihe 2, Knopf 5 / Reihe 4, Knopf 4 |
| `-1` | **2. Zwischenraum (2–3)** | `A` | `4` | Reihe 1, Knopf 6 / Reihe 3, Knopf 5 |
| **`0`** | **3. Linie (Mittellinie)** | **`B`** | **`4`** | **Reihe 2, Knopf 6 (Gleichton)** / Reihe 4, Knopf 5 |
| **`+1`** | **3. Zwischenraum (3–4)** | **`C`** | **`5`** | Reihe 1, Knopf 7 / **Reihe 3, Knopf 6 (Gleichton)** |
| **`+2`** | **4. Linie** | **`D`** | **`5`** | Reihe 2, Knopf 7 / **Reihe 4, Knopf 6 (Gleichton)** |
| `+3` | **4. Zwischenraum (4–5)** | `E` | `5` | Reihe 1, Knopf 8 / Reihe 3, Knopf 7 |
| `+4` | **5. Linie (oben)** | `F` | `5` | Reihe 2, Knopf 8 / Reihe 4, Knopf 7 |
| `+5` | Raum über 5. Linie | `G` | `5` | Reihe 1, Knopf 9 / Reihe 3, Knopf 8 |
| `+6` | 1. Hilfslinie oben | `A` | `5` | Reihe 2, Knopf 9 / Reihe 4, Knopf 8 |
| `+7` | Raum über 1. Hilfslinie oben | `B` | `5` | Reihe 1, Knopf 10 / Reihe 3, Knopf 9 |
| `+8` | 2. Hilfslinie oben | `C` | `6` | Reihe 2, Knopf 10 / Reihe 4, Knopf 9 |

> [!WARNING]
> **Wichtige Regel für Vorzeichen in Griffschrift:**
> Ein Griffschrift-Notensystem hat am Zeilenanfang **niemals Generalvorzeichen** (in MusicXML zwingend `<fifths>0</fifths>`), selbst wenn das Originalstück oben in F-Dur, G-Dur oder Es-Dur steht!
> Ein Vorzeichen (`#` oder `b`) direkt vor einer Griffschrift-Note bedeutet **nicht** „Ton um einen Halbton erhöhen“, sondern kennzeichnet eine **physische Sondertaste (Halbtontaste am oberen Rand des Griffbretts, meist Knopf 1 oder 2)**!

---

## 4. Darstellung der Balgrichtung (`DRUCK` vs. `ZUG`)

Da ein Notenkopf z. B. auf der 2. Linie (`Reihe 2, Knopf 5`) sowohl auf `DRUCK` ($e''$) als auch auf `ZUG` ($f''$) gedrückt werden kann, muss die Balgrichtung im Notenbild markiert werden:

1. **Im System Rosenzopf (Klassischer Standard):**
   * **`DRUCK` (Zusammendrücken):** Unter dem Notensystem verläuft ein **dicker horizontaler schwarzer Balken (Druckbalken)** über die gesamte Dauer der Druck-Passage.
   * **`ZUG` (Auseinanderziehen):** **Kein Balken** unter dem System.
2. **Alternative Farbdarstellung (z. B. manche Lernsysteme):**
   * Rot = Druck, Schwarz/Blau = Zug (für PDF-Druck auf Schwarz-Weiß-Druckern ist jedoch der **Druckbalken** unverzichtbar).

In **MusicXML** lässt sich der Druckbalken über einen durchgehenden `<bracket>`-Spanner (`<direction-type><bracket type="start" line-end="none" line-type="solid"/></direction-type>`) unterhalb des Systems (`placement="below"`) darstellen.

---

## 5. Bass-Notation in der Griffschrift (Falle Nr. 2!)

In der Griffschrift werden die Bass- und Akkordtasten der linken Hand als **Buchstaben** unter (oder über) dem Notensystem notiert.

> [!CAUTION]
> **Verwechslungsgefahr für Programmierer und Musiker:**
> Die Bass-Buchstaben `A`, `B`, `C`, `D` (bzw. `F`) in der Griffschrift sind **keine Tonnamen**, sondern **abstrakte Reihen-Nummern (1 bis 4)**!
> * Ein **`B`** in der Griffschrift bedeutet **immer „Grundbass der 2. Reihe“** (auf einer `G-C-F-B`-Harmonika klingt dort auf Druck ein **C-Bass** und auf Zug ein **G-Bass**, niemals ein B!).

### Codierungs-Tabelle der Bass-Buchstaben (System Rosenzopf):

| Griffschrift-Symbol | Bedeutung (Hardware-Taste linke Hand) | Klingender Ton/Akkord bei `G-C-F-B` auf **DRUCK** | Klingender Ton/Akkord bei `G-C-F-B` auf **ZUG** |
| :---: | :--- | :--- | :--- |
| **`A`** *(Groß)* | **Grundbass** zur **1. Reihe** | `G` (tiefer Helikonbass) | `D` (tiefer Helikonbass) |
| **`a`** *(klein)* | **Akkordbass** zur **1. Reihe** | `G-Dur`-Akkord | `D-Dur`-Akkord |
| **`B`** *(Groß)* | **Grundbass** zur **2. Reihe** *(Hauptreihe)* | `C` (tiefer Helikonbass) | `G` (tiefer Helikonbass) |
| **`b`** *(klein)* | **Akkordbass** zur **2. Reihe** | `C-Dur`-Akkord | `G-Dur`-Akkord |
| **`C`** *(Groß)* | **Grundbass** zur **3. Reihe** | `F` (tiefer Helikonbass) | `C` (tiefer Helikonbass) |
| **`c`** *(klein)* | **Akkordbass** zur **3. Reihe** | `F-Dur`-Akkord | `C-Dur`-Akkord |
| **`D`** *(oder **`F`**)* | **Grundbass** zur **4. Reihe** | `B` (`Bb`, Helikonbass) | `F` (tiefer Helikonbass) |
| **`d`** *(oder **`f`**)* | **Akkordbass** zur **4. Reihe** | `B-Dur`-Akkord | `F-Dur`-Akkord |

*(Zusatzbässe wie Wechselbässe/Terzbässe werden durch einen kleinen Querstrich über oder unter dem Großbuchstaben markiert, z. B. $\underline{B}$ oder $\overline{B}$).*
