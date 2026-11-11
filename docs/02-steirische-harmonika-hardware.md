# 02 – Die Steirische Harmonika als Hardware-System

Aus Sicht der Informatik ist eine Steirische Harmonika kein lineares Tasteninstrument (wie ein Klavier), sondern eine **zustandsbehaftete Matrix-Tastatur** mit zwei gekoppelten Eingabefeldern:
1. **Diskant (Rechte Hand):** 3 bis 5 Reihen (Standard: **4 Reihen**) mit insgesamt ca. 46 Melodie-Knöpfen.
2. **Bass (Linke Hand):** 2 Reihen mit ca. 15 bis 16 Bass- und Akkord-Knöpfen.
3. **Balg (Mitte):** Globaler Zustandsschalter zwischen **`DRUCK`** (Zusammendrücken) und **`ZUG`** (Auseinanderziehen).

---

## 1. Die zwei Grundprinzipien: Diatonisch & Wechseltönig

### A. Wechseltönig (Bisonorisch = Globaler Shift-State)
Auf einem Klavier erzeugt jede Taste immer denselben Ton. Auf der Steirischen Harmonika sitzen unter jedem Knopf **zwei verschiedene Stimmzungen-Paare** (mit gegenläufigen Ventilen):
* Drückt man den Balg zusammen (**`DRUCK`**), strömt die Luft in Richtung A $\rightarrow$ Ton $p_{\text{Druck}}$ erklingt.
* Zieht man den Balg auseinander (**`ZUG`**), strömt die Luft in Richtung B $\rightarrow$ Ton $p_{\text{Zug}}$ erklingt.

> [!IMPORTANT]
> **Globaler Hardware-Constraint:**
> Da es nur einen einzigen Balg gibt, gilt der Zustand `direction` $\in \{\text{DRUCK}, \text{ZUG}\}$ zu jedem Zeitpunkt $t$ **global für alle gleichzeitig gedrückten Knöpfe** (sowohl für alle Finger der rechten Hand als auch für die Bass-Knöpfe der linken Hand!).

### B. Diatonisch (Tonleiter-gebunden)
Eine einzelne Knopfreihe enthält nicht alle 12 Halbtöne einer Oktave, sondern nur die **7 Stammtöne einer bestimmten Dur-Tonleiter** (z. B. C-Dur in Reihe 2). Um andere Tonarten spielen zu können, hat das Instrument 4 parallele Reihen, die jeweils im Abstand von **+5 Halbtönen (einer Quarte)** zueinander gestimmt sind.

---

## 2. Das mathematische Bildungsgesetz einer Reihe

Warum sind die Töne auf `DRUCK` und `ZUG` scheinbar so unregelmäßig verteilt? Dahinter steckt eine geniale **Ergonomie-Optimierung für Akkordgriffe**:

### Auf `DRUCK`: Reine Dur-Dreiklänge (Tonika)
Drückt man in einer Reihe (z. B. der 2. Reihe = C-Dur) nacheinander die Knöpfe von unten nach oben auf **`DRUCK`**, erklingen **ausschließlich die 3 Töne des Grund-Dreiklangs** (`C – E – G – C – E – G – C ...`):
* **Ergonomie-Vorteil:** Egal welche 2 oder 3 direkt benachbarten Knöpfe man in derselben Reihe auf `DRUCK` gleichzeitig drückt – es entsteht **immer** ein wohlklingender Zweiklang (Terz/Sext) oder Dreiklang der Haupttonart!

### Auf `ZUG`: Die übrigen Tonleitertöne (Dominante / G7)
Auf **`ZUG`** liegen auf denselben Knöpfen die fehlenden Töne der Tonleiter sowie die Töne des Spannungsakkords (Dominantseptakkord, in C-Dur: `D – F – G – H – D – F ...`):
* Auch hier gilt: Zwei benachbarte Knöpfe derselben Reihe ergeben auf `ZUG` fast automatisch einen passenden zweistimmigen Griff für die Dominante (`G7`).

### Der „Gleichton“ (Das Symmetrie-Element)
Ein Dur-Dreiklang (`DRUCK`) hat **3** Töne pro Oktave (`C, E, G`). Ein Dominantseptakkord (`ZUG`) hat aber **4** Töne pro Oktave (`D, F, G, H`).
Wenn man einfach abwechselnd 3 Drucktöne und 4 Zugtöne auf die Knöpfe verteilen würde, würden sich die Oktaven von `DRUCK` und `ZUG` mit jedem Knopf weiter gegeneinander verschieben!

**Die Lösung des Instrumentenbaus – der Gleichton (Knopf 6):**
* In der Mitte der Reihe (in der 2., 3. und 4. Reihe jeweils auf **Knopf 6**) wird auf `ZUG` derselbe Ton eingebaut wie auf `DRUCK` (der 5. Ton der Tonleiter, z. B. `g''` in der C-Reihe).
* Dadurch bleibt das Griffmuster über die wichtigsten Spiel-Oktaven synchron, und der Spieler hat einen zentralen **Orientierungsknopf**, der unabhängig von der Balgrichtung immer gleich klingt.
* **Ausnahme 1. Reihe:** Im klassischen System (Rosenzopf / traditionelle 4-Reiher) besitzt die **1. Reihe keinen Gleichton** (bzw. nur bei speziellen Sonderbauten).

---

## 3. Das `+5`-Halbton-Gesetz zwischen den Reihen

Für die Software-Modellierung ist folgende Eigenschaft entscheidend:
Die **2., 3. und 4. Reihe** sind in ihrem Kernbereich **exakt identisch aufgebaut**, nur jeweils um **`+5` Halbtöne (MIDI `+5`)** nach oben transponiert!

Für eine **`G-C-F-B`**-Harmonika gilt:
* **1. Reihe (Außen):** Grundton **G** (G-Dur)
* **2. Reihe:** Grundton **C** = `G + 5 Halbtöne` (C-Dur)
* **3. Reihe:** Grundton **F** = `C + 5 Halbtöne` (F-Dur)
* **4. Reihe (Innen):** Grundton **B** (int. `Bb`) = `F + 5 Halbtöne` (B-Dur)

$$\text{pitch}(\text{row} + 1, \text{button}, \text{dir}) = \text{pitch}(\text{row}, \text{button}, \text{dir}) + 5 \quad (\text{für } \text{row} \in \{2, 3\})$$

---

## 4. Referenz-Belegungstabelle: Standard-Stimmung `G-C-F-B` (Diskant)

> [!NOTE]
> **Knopf-Nummerierung & Akustischer MIDI-Pitch (8'-Grundreihe):**
> Knopf `1` ist physisch der **oberste Knopf** (am nächsten zum Kinn des Spielers, **tiefste** Töne). Beim Spielen wandert die Hand für höhere Töne Richtung Boden (größere Knopf-Nummer).
> In Klammern steht jeweils der **akustisch gemessene MIDI-Pitch der 8'-Grundreihe** ($60 = c' = 261{,}63\text{ Hz}$, Gleichton der 2. Reihe = $g' = \text{MIDI } 67 = 392{,}0\text{ Hz}$). *(Hinweis: In mancher Harmonika-Literatur werden alle Oktavstriche eine Oktave höher geschrieben, akustisch liegen die Grundfrequenzen jedoch exakt bei den hier angegebenen MIDI-Werten).*

| Knopf-Nr. | 1. Reihe (`G`) | 2. Reihe (`C`) | 3. Reihe (`F`) | 4. Reihe (`B` / `Bb`) |
| :---: | :--- | :--- | :--- | :--- |
| **1** *(Zusatz/Halbton)* | Druck: $gis$ (`56`)<br>Zug: $gis$ (`56`) | Druck: $c$ (`48`)<br>Zug: $f$ (`53`) | Druck: $f$ (`53`)<br>Zug: $b$ (`58`) | Druck: $b$ (`58`)<br>Zug: $es'$ (`63`) |
| **2** | Druck: $cis'$ (`61`)<br>Zug: $cis'$ (`61`) | Druck: $e$ (`52`)<br>Zug: $g$ (`55`) | Druck: $a$ (`57`)<br>Zug: $c'$ (`60`) | Druck: $d'$ (`62`)<br>Zug: $f'$ (`65`) |
| **3** | Druck: $d$ (`50`)<br>Zug: $fis$ (`54`) | Druck: $g$ (`55`)<br>Zug: $h$ (`59`) | Druck: $c'$ (`60`)<br>Zug: $e'$ (`64`) | Druck: $f'$ (`65`)<br>Zug: $a'$ (`69`) |
| **4** | Druck: $g$ (`55`)<br>Zug: $a$ (`57`) | Druck: $c'$ (`60`)<br>Zug: $d'$ (`62`) | Druck: $f'$ (`65`)<br>Zug: $g'$ (`67`) | Druck: $b'$ (`70`)<br>Zug: $c''$ (`72`) |
| **5** | Druck: $h$ (`59`)<br>Zug: $c'$ (`60`) | Druck: $e'$ (`64`)<br>Zug: $f'$ (`65`) | Druck: $a'$ (`69`)<br>Zug: $b'$ (`70`) | Druck: $d''$ (`74`)<br>Zug: $es''$ (`75`) |
| **6 (Gleichton)** | Druck: $d'$ (`62`)<br>Zug: $e'$ (`64`) | **Druck: $g'$ (`67`)**<br>**Zug: $g'$ (`67`)** | **Druck: $c''$ (`72`)**<br>**Zug: $c''$ (`72`)** | **Druck: $f''$ (`77`)**<br>**Zug: $f''$ (`77`)** |
| **7** | Druck: $g'$ (`67`)<br>Zug: $fis'$ (`66`) | Druck: $c''$ (`72`)<br>Zug: $h'$ (`71`) | Druck: $f''$ (`77`)<br>Zug: $e''$ (`76`) | Druck: $b''$ (`82`)<br>Zug: $a''$ (`81`) |
| **8** | Druck: $h'$ (`71`)<br>Zug: $a'$ (`69`) | Druck: $e''$ (`76`)<br>Zug: $d''$ (`74`) | Druck: $a''$ (`81`)<br>Zug: $g''$ (`79`) | Druck: $d'''$ (`86`)<br>Zug: $c'''$ (`84`) |
| **9** | Druck: $d''$ (`74`)<br>Zug: $c''$ (`72`) | Druck: $g''$ (`79`)<br>Zug: $f''$ (`77`) | Druck: $c'''$ (`84`)<br>Zug: $b''$ (`82`) | Druck: $f'''$ (`89`)<br>Zug: $es'''$ (`87`) |
| **10** | Druck: $g''$ (`79`)<br>Zug: $e''$ (`76`) | Druck: $c'''$ (`84`)<br>Zug: $a''$ (`81`) | Druck: $f'''$ (`89`)<br>Zug: $d'''$ (`86`) | Druck: $b'''$ (`94`)<br>Zug: $g'''$ (`91`) |
| **11** | Druck: $h''$ (`83`)<br>Zug: $fis''$ (`78`) | Druck: $e'''$ (`88`)<br>Zug: $h''$ (`83`) | Druck: $a'''$ (`93`)<br>Zug: $e'''$ (`88`) | – |
| **12** | Druck: $d'''$ (`86`)<br>Zug: $a''$ (`81`) | Druck: $g'''$ (`91`)<br>Zug: $d'''$ (`86`) | – | – |

### Beobachtung der Redundanz (Mehrdeutigkeit):
Schau dir in der Tabelle den Ton **$c'$ (MIDI `60`)** an. Er existiert **4-mal** auf dem Instrument:
1. `(Reihe 1, Knopf 5, ZUG)`
2. `(Reihe 2, Knopf 4, DRUCK)`
3. `(Reihe 3, Knopf 3, DRUCK)`
4. `(Reihe 3, Knopf 2, ZUG)`

Genau deshalb ist die Rückübersetzung `MIDI -> Griffschrift` keine 1:1-Tabellenabfrage, sondern ein Optimierungsproblem!

---

## 5. Andere Harmonika-Stimmungen (Transpositions-Tabelle)

Wenn ein Nutzer eine Harmonika mit einer anderen Stimmung besitzt, ändert sich am internen Aufbau des Instruments **nichts** – lediglich das gesamte Array aller MIDI-Werte verschiebt sich um einen konstanten Integer-Offset $\Delta p$:

| Stimmung | Reihen-Grundtöne (1–4) | Offset $\Delta p$ relativ zu `G-C-F-B` |
| :--- | :--- | :---: |
| **`F-B-Es-As`** | F – Bb – Eb – Ab | **`-2`** Halbtöne |
| **`Fis-H-E-A`** | F# – B – E – A | **`-1`** Halbton |
| **`G-C-F-B`** *(Referenz)* | G – C – F – Bb | **`0`** Halbtöne |
| **`Gis-Cis-Fis-H`** | G# – C# – F# – B | **`+1`** Halbton |
| **`A-D-G-C`** | A – D – G – C | **`+2`** Halbtöne |
| **`B-Es-As-Des`** *(sehr häufig!)* | Bb – Eb – Ab – Db | **`+3`** Halbtöne |

---

## 6. Die Bass-Seite (Linke Hand) und das Harmonie-Orakel

Auf der linken Seite bedient der Spieler zwei Arten von Knöpfen (meist im Wechsel zwischen Ringfinger und Zeigefinger – das typische *„Um-Pa / Grundbass-Akkord“*):
1. **Grundbässe (Helikonbässe):** Spielen einen einzelnen, extrem tiefen und obertonreichen Basston.
2. **Akkordbässe:** Spielen gleichzeitig einen 3-stimmigen Begleitakkord.

### Die Kopplung an `DRUCK` und `ZUG`
Zu jeder Diskant-Reihe gehört ein festes Paar aus Grundbass + Akkordbass:

| Zugehörige Diskant-Reihe (bei `G-C-F-B`) | Bass + Akkord auf `DRUCK` (Tonika / I. Stufe) | Bass + Akkord auf `ZUG` (Dominante / V. Stufe) |
| :--- | :--- | :--- |
| **1. Reihe (`G`)** | **G-Bass** + **G-Dur-Akkord** (`G-H-D`) | **D-Bass** + **D-Dur-Akkord** (`D-Fis-A`) |
| **2. Reihe (`C`)** | **C-Bass** + **C-Dur-Akkord** (`C-E-G`) | **G-Bass** + **G-Dur-Akkord** (`G-H-D`) |
| **3. Reihe (`F`)** | **F-Bass** + **F-Dur-Akkord** (`F-A-C`) | **C-Bass** + **C-Dur-Akkord** (`C-E-G`) |
| **4. Reihe (`B`)** | **B-Bass** + **B-Dur-Akkord** (`B-D-F`) | **F-Bass** + **F-Dur-Akkord** (`F-A-C`) |

> [!TIP]
> **Warum der Bass unser „Zug/Druck-Orakel“ für den Algorithmus ist:**
> Wenn ein Musikstück in **C-Dur** (2. Reihe) gespielt wird und im Takt die Harmonie **C-Dur** erklingt, **muss** der Spieler fast zwingend auf **`DRUCK`** sein, weil der C-Dur-Akkordbass der 2. Reihe nur auf `DRUCK` existiert!
> Wechselt das Lied im nächsten Takt auf den Spannungsakkord **G-Dur / G7**, **muss** der Spieler in der 2. Reihe auf **`ZUG`** wechseln!
> Allein durch die Erkennung des Basses/Akkords im Audio oder MusicXML ist die Balgrichtung (`DRUCK` vs. `ZUG`) bereits zu über **90 % eindeutig determiniert**.
