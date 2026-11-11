# Fachliche & Algorithmische Dokumentation (Harmonica / Griffschrift)

Diese Dokumentation erklärt alle notwendigen Konzepte aus **Musiktheorie**, **Instrumentenbau (Steirische Harmonika)**, **Griffschrift-Notation** und **Algorithmik** aus der Perspektive der **Informatik**. Es wird kein musikalisches Vorwissen vorausgesetzt.

---

## Dokumenten-Übersicht

1. **[01 – Musiktheorie für Informatiker](./01-musiktheorie-fuer-informatiker.md)**
   * Frequenzen, Oktaven und der **MIDI-Pitch-Standard (`0..127`)**
   * Modulo-12-Arithmetik, Stammtöne vs. Halbtöne (`#` / `b`) und die deutsche `H`/`B`-Falle
   * Tonleitern (Offset-Arrays), Akkorde (Tonika vs. Dominante) und Transposition als Vektor-Addition
   * Zeit-Quantisierung (BPM, Takte `2/4`, `3/4`, `4/4`, Notendauern) und das 5-Linien-Koordinatensystem

2. **[02 – Die Steirische Harmonika als Hardware-System](./02-steirische-harmonika-hardware.md)**
   * Wechseltönigkeit als globaler Hardware-Shift-Zustand (**`DRUCK`** vs. **`ZUG`**)
   * Diatonischer Aufbau: Warum `DRUCK` reine Dur-Dreiklänge und `ZUG` den Spannungsakkord liefert
   * Der **Gleichton (Knopf 6)** als Symmetrie-Anker und das **`+5`-Halbton-Gesetz** zwischen den Reihen
   * Vollständige **Referenz-Tastenbelegung (`G-C-F-B`)** mit MIDI-Pitch-Werten
   * Andere Stimmungen (`A-D-G-C`, `B-Es-As-Des`) und das **Bass-Harmonie-Orakel** der linken Hand

3. **[03 – Griffschrift-Spezifikation (System Max Rosenzopf)](./03-griffschrift-spezifikation.md)**
   * Griffschrift als Hardware-Keycode-Notation im 5-Linien-Gewand
   * Gerade Reihen (`2`, `4`) auf den Linien vs. ungerade Reihen (`1`, `3`) in den Zwischenräumen
   * Runde Notenköpfe (`●`, Reihe 1 & 2) vs. Kreuz-Notenköpfe (`×`, Reihe 3 & 4)
   * Die zentrale Abbildungsformel: $\text{staffStep}(\text{row}, \text{button}) = (\text{row} - 2) + 2 \cdot (\text{button} - 6)$
   * MusicXML Fake-Pitch-Mapping, Druckbalken, Sondertasten und die Bass-Buchstaben (`A/a`, `B/b`, `C/c`, `D/d`)

4. **[04 – Algorithmik & Übersetzungs-Pipeline](./04-algorithmik-und-pipeline.md)**
   * Akustische Störfaktoren bei der Audio-KI (Schwebung/Tremolo, Helikonbässe) und Domänen-Filter
   * Automatische Transposition in spielbare Harmonika-Tonarten
   * Der **Viterbi-Algorithmus (Dynamische Programmierung auf einem DAG)** für optimale Knopf- und Balgauswahl
   * Interaktives User-Override (Constraint Injection) und Dual-Track MusicXML $\rightarrow$ Verovio $\rightarrow$ PDF

---

## Kurz-Glossar (Musik $\leftrightarrow$ Informatik)

| Fachbegriff (Musik / Harmonika) | Informatik-Äquivalent |
| :--- | :--- |
| **Tonhöhe (Pitch)** | Integer `0..127` (MIDI-Standard, $60 = c' = 261{,}63\text{ Hz}$) |
| **Halbton (Semitone)** | Kleinste Schrittweite `+1` / `-1` im MIDI-Raum |
| **Oktave** | `pitch + 12` (Frequenzverdopplung; gleiche Tonklasse `pitch % 12`) |
| **Transponieren** | Konstante Offset-Addition `pitch + delta` auf alle Noten eines Stücks |
| **Takt (Measure / Bar)** | Zeit-Bucket fester Länge (z. B. `3/4` = Platz für drei Viertelnoten) |
| **Quantisierung** | Grid-Snapping von Millisekunden-Zeitstempeln auf diskrete Brüche (`1/4`, `1/8`, `1/16`) |
| **Diskant (Rechte Hand)** | 4×12 Matrix-Tastatur für die Melodie |
| **Bass (Linke Hand)** | Begleit-Tasten für Grundbass (Tiefton) und Akkordbass (3-Klänge) |
| **Wechseltönig (`DRUCK` / `ZUG`)** | Globaler Hardware-Modifier (wie eine `Shift`-Taste), der die Belegung aller Knöpfe umschaltet |
| **Gleichton (Knopf 6)** | Fixpunkt in Reihe 2, 3, 4 mit `pitch(DRUCK) == pitch(ZUG)`; Ursprung (`staffStep = 0`) der Griffschrift |
| **Normalnotation** | Output-orientierte Notation (speichert die Ziel-Frequenz `pitch`) |
| **Griffschrift** | Input-orientierte Scancode-Notation (speichert `(row, button, direction)`) |
