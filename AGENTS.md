# AGENTS.md – Projekt-Orientierung & Domänen-Regeln

Dieses Dokument dient KI-Agenten und Entwicklern als zentrale Orientierung im Repository `harmonica`. Lies vor größeren Architektur- oder Algorithmus-Änderungen die verlinkten Spezifikationen in [`docs/`](./docs/README.md).

---

## 1. Projektziel

Entwicklung einer Pipeline und (Android-)Applikation, die Musikaufnahmen (Audio) bzw. standardisierte Notendateien (MIDI / MusicXML) von Volksmusik / Steirischer Harmonika verarbeitet, automatisch in eine spielbare **Griffschrift (System Max Rosenzopf)** übersetzt und **Normalnoten + Griffschrift gemeinsam untereinander** als druckfertiges PDF rendert.

---

## 2. Dokumentation (`docs/`)

Der Entwickler/User hat **kein musiktheoretisches Vorwissen** (Informatik-Hintergrund). Erkläre musikalische Sachverhalte immer über Datenstrukturen, Integer-Arithmetik (MIDI-Pitch), Zustandsautomaten und Graphentheorie.

* **[`docs/README.md`](./docs/README.md)** – Einstiegspunkt und Kurz-Glossar (Musik $\leftrightarrow$ Informatik)
* **[`docs/01-musiktheorie-fuer-informatiker.md`](./docs/01-musiktheorie-fuer-informatiker.md)** – MIDI-Pitch (`0..127`), Modulo-12-Arithmetik, Tonleitern, Transposition, Takte & Quantisierung
* **[`docs/02-steirische-harmonika-hardware.md`](./docs/02-steirische-harmonika-hardware.md)** – Hardware-Logik (`DRUCK` vs. `ZUG`), Gleichton, `+5`-Halbton-Gesetz zwischen den Reihen, vollständige `G-C-F-B`-Referenztabelle und Bass-Kopplung
* **[`docs/03-griffschrift-spezifikation.md`](./docs/03-griffschrift-spezifikation.md)** – Formale Griffschrift-Regeln, Koordinaten-Formel, MusicXML-Mapping (`staffStep` $\rightarrow$ Fake-Pitch) und Bass-Notation
* **[`docs/04-algorithmik-und-pipeline.md`](./docs/04-algorithmik-und-pipeline.md)** – Audio-Filterung (Tremolo, Helikonbässe), automatische Transposition und Viterbi-Optimierung (DAG Shortest Path)

---

## 3. Kritische Domänen-Invarianten (Unbedingt beachten!)

Bei der Implementierung von Datenmodellen, Algorithmen und MusicXML-Generatoren gelten folgende unumstößliche Regeln:

1. **Deutsche vs. Internationale Notennamen (`B` vs. `Bb`):**
   * Im deutschen Sprachraum (z. B. Stimmung `G-C-F-B`) steht **`B`** für das internationale **`Bb` (B-flat, `pitch % 12 == 10`, z. B. MIDI `58`, `70`, `82`)**.
   * Der Ton ein Halbton unter `C` heißt deutsch **`H`** (international `B`, `pitch % 12 == 11`, z. B. MIDI `59`, `71`, `83`).
   * In MusicXML (`<step>`) wird immer die internationale Bezeichnung (`B` mit `<alter>-1</alter>` für deutsches `B`) verwendet.

2. **Globaler Balgzustand (`DRUCK` vs. `ZUG`):**
   * Zu jedem Zeitpunkt $t$ müssen **alle gleichzeitig gespielten Töne** (alle Diskant-Noten + Bass/Akkord) **exakt dieselbe Balgrichtung** (`DRUCK` oder `ZUG`) besitzen. Kombinationen mit gemischter Balgrichtung zum selben Zeitpunkt sind physikalisch unmöglich.

3. **Mathematische Griffschrift-Formel (Y-Koordinate & Notenkopf):**
   * Ursprung `staffStep = 0` ist die **mittlere (3.) Notenlinie** (entspricht dem **Gleichton der 2. Reihe = Knopf 6**; im Violinschlüssel Fake-Pitch `B4`).
   * Für jede Reihe `row` $\in \{1, 2, 3, 4\}$ und jeden Knopf `button` $\in \{1 \dots 12\}$ gilt:
     $$\text{staffStep}(\text{row}, \text{button}) = (\text{row} - 2) + 2 \cdot (\text{button} - 6)$$
   * **Ungerade Reihen (`1`, `3`)** landen immer in den **Zwischenräumen** (`staffStep` ungerade).
   * **Gerade Reihen (`2`, `4`)** landen immer **auf den Linien** (`staffStep` gerade).
   * **Notenkopf-Form:**
     * `row in {1, 2}` $\rightarrow$ normaler runder Notenkopf.
     * `row in {3, 4}` $\rightarrow$ Kreuz-Notenkopf (`<notehead>x</notehead>`).

4. **Vorzeichen-Regel in der Griffschrift (`<fifths>0</fifths>`):**
   * Die Griffschrift-Spur darf **niemals Generalvorzeichen am Zeilenanfang** haben (`<fifths>0</fifths>`), auch wenn die Normalnoten-Spur darüber Vorzeichen besitzt.
   * Ein `#` oder `b` direkt vor einem Griffschrift-Notenkopf codiert keine chromatische Erhöhung, sondern eine **physische Sondertaste (Halbtontaste auf Knopf 1 oder 2)**.

5. **Bass-Buchstaben sind Reihen-IDs, keine Tonhöhen:**
   * In der Griffschrift stehen `A/a`, `B/b`, `C/c`, `D/d` (bzw. `F/f`) für **Reihe 1, 2, 3, 4** (Großbuchstabe = Grundbass, Kleinbuchstabe = Akkordbass) und **nicht** für die musikalischen Töne A, B, C, D!

6. **Übersetzungs-Algorithmus (Kein Greedy, sondern Viterbi/DAG):**
   * Da viele MIDI-Töne mehrfach auf der Harmonika existieren, darf nicht isoliert pro Note entschieden werden. Die Übersetzung erfolgt über **Dynamische Programmierung (Viterbi-Algorithmus)** über die Zeitachse unter Berücksichtigung von Handspanne ($\Delta b \le 5$), Reihen-Kontinuität und Balgwechsel-Kosten.

---

## 4. Entwicklungs- & Git-Konventionen

* **Betriebssystem & Shell:** Windows – ausschließlich **PowerShell**-Befehle verwenden (keine Linux-spezifischen Kommandos).
* **Git-Workflow:** Kleine, logisch getrennte, **atomare Commits** (`Atomic commits, multiple commits`) mit sprechenden Commit-Messages (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`).
