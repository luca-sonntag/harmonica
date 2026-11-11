# 01 – Musiktheorie für Informatiker

Dieses Dokument übersetzt die benötigten musikalischen Grundbegriffe (Tonhöhe, Oktave, Tonart, Takt, Normalnotation) in präzise Datenstrukturen und mathematische Konzepte. Es wird **kein** musikalisches Vorwissen vorausgesetzt.

---

## 1. Tonhöhe (Pitch) und Frequenz

Physikalisch ist ein Ton eine periodische Luftdruckschwingung mit einer Grundfrequenz $f$ in Hertz ($\text{Hz}$). Das menschliche Gehör nimmt Frequenzen jedoch **logarithmisch** wahr:
* Eine Verdopplung der Frequenz ($2 \cdot f$) klingt für das Gehirn wie „derselbe Ton, nur eine Stufe höher“. Dieses Intervall nennt man eine **Oktave**.
* In der westlichen Musik wird jede Oktave in **12 gleich große Schritte (Halbtöne / Semitones)** unterteilt.

### Der MIDI-Standard (Integer-Codierung)
In der Softwareentwicklung rechnet man fast nie mit krummen Frequenzen in $\text{Hz}$, sondern mit dem **MIDI-Pitch** ($p \in \{0 \dots 127\}$):

$$f(p) = 440\text{ Hz} \cdot 2^{\frac{p - 69}{12}}$$

Umgekehrt gilt:
* `p + 1` = **1 Halbton höher** (Faktor $2^{1/12} \approx 1{,}05946$)
* `p + 12` = **1 Oktave höher** (Faktor $2$)

| MIDI-Pitch `p` | Deutscher Notenname | International / Wissenschaftlich | Frequenz $f$ | Bedeutung |
| :---: | :---: | :---: | :---: | :--- |
| `48` | $c$ | `C3` | $130{,}81\text{ Hz}$ | Kleines C (Bassbereich) |
| `60` | $c'$ | `C4` | $261{,}63\text{ Hz}$ | **Eingestrichenes C** („Mittleres C“) |
| `69` | $a'$ | `A4` | $440{,}00\text{ Hz}$ | Kammerton A (Kalibrierungsstandard) |
| `72` | $c''$ | `C5` | $523{,}25\text{ Hz}$ | Zweigestrichenes C |
| `84` | $c'''$ | `C6` | $1046{,}50\text{ Hz}$ | Dreigestrichenes C |

> [!IMPORTANT]
> **Deutsche vs. Internationale Schreibweise (Falle Nr. 1):**
> Im deutschen Sprachraum (und in fast jeder Literatur zur Steirischen Harmonika!) heißt der Ton ein Halbton unter `C` **`H`** (MIDI `59`, `71`), während der Ton noch einen Halbton tiefer **`B`** heißt (international: **`Bb`** / B-flat, MIDI `58`, `70`).
> Wenn eine Harmonika die Stimmung **`G-C-F-B`** hat, ist mit `B` also **immer das internationale `Bb` (`B-flat`)** gemeint!

---

## 2. Modulo-12-Arithmetik: Die 12 Töne einer Oktave

Da sich nach 12 Halbtönen alles wiederholt, lässt sich jede Tonklasse über `pitch % 12` beschreiben:

| `pitch % 12` | MIDI (Oktave 4) | Stammton (Weiße Klaviertaste) | Halbtöne / Alterierte Töne (Schwarze Klaviertaste) |
| :---: | :---: | :---: | :--- |
| `0` | `60` | **C** | – |
| `1` | `61` | – | **Cis** (`C#`) / **Des** (`Db`) |
| `2` | `62` | **D** | – |
| `3` | `63` | – | **Dis** (`D#`) / **Es** (`Eb`) |
| `4` | `64` | **E** | – |
| `5` | `65` | **F** | – |
| `6` | `66` | – | **Fis** (`F#`) / **Ges** (`Gb`) |
| `7` | `67` | **G** | – |
| `8` | `68` | – | **Gis** (`G#`) / **As** (`Ab`) |
| `9` | `69` | **A** | – |
| `10` | `70` | – | **Ais** (`A#`) / **B** (int. `Bb`) |
| `11` | `71` | **H** (int. `B`) | – |

### Was bedeuten Vorzeichen (`#` und `b`)?
* **`#` (Kreuz / Sharp, Endung „-is“):** Addiert `+1` zum MIDI-Pitch des Stammtons (z. B. `F` = `65` $\rightarrow$ `Fis` = `66`).
* **`b` (Be / Flat, Endung „-es“):** Subtrahiert `-1` vom MIDI-Pitch des Stammtons (z. B. `E` = `64` $\rightarrow$ `Es` = `63`).
* **Enharmonische Verwechslung:** `Fis` und `Ges` haben exakt denselben MIDI-Pitch (`66`) und dieselbe Frequenz. Sie sind nur zwei verschiedene Variablennamen für denselben Integer-Wert.

---

## 3. Tonleitern (Scales), Tonarten (Keys) und Transposition

Ein normales Musikstück nutzt nicht alle 12 Halbtöne gleichberechtigt, sondern wählt eine **7-elementige Teilmenge** aus den 12 Tönen aus. Diese Teilmenge nennt man eine **diatonische Tonleiter (Dur-Tonleiter)**.

### Das Abstands-Array einer Dur-Tonleiter
Von einem Start-Ton `root` aus erhält man die 7 Töne einer Dur-Tonleiter immer durch Addition desselben Offset-Arrays:

```kotlin
val MAJOR_SCALE_OFFSETS = intArrayOf(0, 2, 4, 5, 7, 9, 11)
```

* **Beispiel 1: C-Dur (`root = 60`):**
  `[60, 62, 64, 65, 67, 69, 71]` $\rightarrow$ `[C, D, E, F, G, A, H]` (nur Stammtöne, 0 Vorzeichen).
* **Beispiel 2: G-Dur (`root = 67`):**
  `[67, 69, 71, 72, 74, 76, 78]` $\rightarrow$ `[G, A, H, C, D, E, Fis]` (enthält `Fis` statt `F`).
* **Beispiel 3: F-Dur (`root = 65`):**
  `[65, 67, 69, 70, 72, 74, 76]` $\rightarrow$ `[F, G, A, B, C, D, E]` (enthält `B` [int. `Bb`] statt `H`).

### Akkorde (Mehrklänge)
Werden mehrere Töne gleichzeitig gespielt, spricht man von einem Zweiklang (2 Töne) oder Akkord (ab 3 Tönen):
* **Dur-Dreiklang (Tonika / Grundakkord):** Besteht aus dem 1., 3. und 5. Ton der Tonleiter, also den Offsets **`[0, +4, +7]`** Halbtöne vom Grundton (z. B. C-Dur = `C, E, G` = `[60, 64, 67]`).
* **Dominantseptakkord (Spannungsakkord auf der 5. Stufe):** Besteht aus dem 5., 7., 2. und 4. Ton der Tonleiter (z. B. in C-Dur ist das **G7** = `G, H, D, F`). In der Volksmusik wechseln sich fast immer **Tonika (Ruhe)** und **Dominante (Spannung)** ab.

### Was ist „Transponieren“?
Transponieren ist eine **konstante Vektor-Addition** auf alle `pitch`-Werte eines Musikstücks:

```kotlin
fun transpose(notes: List<NoteEvent>, semitoneShift: Int): List<NoteEvent> =
    notes.map { it.copy(pitch = it.pitch + semitoneShift) }
```

Da alle Abstände zwischen den Noten gleich bleiben, bleibt die Melodie für das menschliche Ohr identisch – sie liegt nur insgesamt höher oder tiefer.

---

## 4. Zeit, Takt (Measure) und Quantisierung

Auf der Zeitachse arbeitet geschriebene Musik nicht mit Millisekunden, sondern mit **relativen Brüchen eines Taktes (Measure / Bar)**.

### Das Zeitraster
1. **Tempo (BPM – Beats Per Minute):** Gibt an, wie viele Grundschläge (meist Viertelnoten) pro Minute vergehen. Bei `120 BPM` dauert ein Viertelschlag exakt $500\text{ ms}$.
2. **Taktart (Time Signature):** Ein Bruch am Anfang des Stücks, der definiert, wie groß ein Takt-Bucket ist:
   * **`2/4`-Takt (typisch für Polka, Marsch):** Jeder Takt fasst den Wert von **2 Viertelnoten** (*„Eins – Zwei | Eins – Zwei“*).
   * **`3/4`-Takt (typisch für Walzer, Landler):** Jeder Takt fasst den Wert von **3 Viertelnoten** (*„Eins – Zwei – Drei | Eins – Zwei – Drei“*).
   * **`4/4`-Takt (typisch für Boarischer):** Jeder Takt fasst den Wert von **4 Viertelnoten**.
3. **Notendauern (Durations):**
   Jede Note belegt einen Bruchteil eines `4/4`-Taktes:
   * Ganze Note (`1/1`) = 4 Viertelschläge
   * Halbe Note (`1/2`) = 2 Viertelschläge (hohler Notenkopf mit Hals)
   * Viertelnote (`1/4`) = 1 Viertelschlag (ausgemalter Notenkopf mit Hals)
   * Achtelnote (`1/8`) = 0,5 Viertelschläge (mit 1 Fähnchen oder 1 Querbalken)
   * Sechzehntelnote (`1/16`) = 0,25 Viertelschläge (mit 2 Fähnchen oder 2 Querbalken)
   * **Punktierte Note (`.` hinter dem Notenkopf):** Verlängert die Dauer der Note um den Faktor $1{,}5$ (z. B. punktierte Viertel = $1/4 + 1/8 = 3/8$).

---

## 5. Normalnotation als 2D-Koordinatensystem

Ein herkömmliches Notensystem besteht aus **5 horizontalen Linien** (gezählt von unten = Linie 1 bis oben = Linie 5) und den **4 Zwischenräumen** dazwischen.

* **Wichtig:** Auf der Y-Achse der Normalnotation wird **nicht** in Halbtönen (`0..11`) gezählt, sondern nur in den **7 Stammtönen (`C, D, E, F, G, A, H`)**!
* Jede Linie und jeder Zwischenraum repräsentiert den nächsten Stammton:
  * Im gängigen **Violinschlüssel (Treble Clef)**:
    * 1. Hilfslinie unter dem System = `C4` ($c'$, MIDI `60`)
    * Raum unter Linie 1 = `D4` (`62`)
    * **Linie 1 (unten)** = `E4` (`64`)
    * Raum 1–2 = `F4` (`65`)
    * **Linie 2** = `G4` (`67`)
    * Raum 2–3 = `A4` (`69`)
    * **Linie 3 (Mitte)** = `H4` (`71`)
    * Raum 3–4 = `C5` ($c''$, `72`)
    * **Linie 4** = `D5` (`74`)
    * Raum 4–5 = `E5` (`76`)
    * **Linie 5 (oben)** = `F5` (`77`)
* Halbtöne wie `Fis` oder `B` haben **keine eigene Linie**, sondern sitzen auf der Linie von `F` bzw. `H` und erhalten ein Vorzeichen (`#` oder `b`) direkt vor den Notenkopf oder global am Zeilenanfang (**Generalvorzeichen**).
