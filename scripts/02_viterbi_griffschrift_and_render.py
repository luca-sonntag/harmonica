"""
Step 2: Polyphonic Chord Quantization, Viterbi Griffschrift Optimization & Verovio Rendering
Takes the transcribed notes from Step 1, extracts 1-to-2-voice Diskant chords + Bass harmony,
runs our Viterbi DAG optimizer, generates a Dual-System MusicXML (Normalnoten + Griffschrift),
and renders SVG/PNG sheet music via Verovio.
"""

import json
import math
from dataclasses import dataclass
from itertools import product
from pathlib import Path
import requests
import verovio


@dataclass(frozen=True)
class ButtonState:
    row: int          # 1..4
    button: int       # 1..12 (6 = Gleichton)
    direction: str    # "DRUCK" or "ZUG"
    pitch: int        # Acoustic MIDI pitch in G-C-F-B reference tuning (67 = G4 Gleichton Row 2)
    is_semitone: bool = False

    @property
    def staff_step(self) -> int:
        """
        Exact Rosenzopf Griffschrift Y-coordinate formula relative to middle line (B4 = 0):
        staffStep(row, button) = (row - 2) + 2 * (button - 6)
        """
        return (self.row - 2) + 2 * (self.button - 6)

    @property
    def notehead(self) -> str:
        return "x" if self.row in (3, 4) else "normal"


# Complete G-C-F-B Reference Hardware Table (Acoustic 8' fundamental MIDI pitches, Gleichton Row 2 = 67)
GCFB_BUTTONS: list[ButtonState] = [
    # Row 1 (G-Dur)
    ButtonState(1, 1, "DRUCK", 56, True), ButtonState(1, 1, "ZUG", 56, True),
    ButtonState(1, 2, "DRUCK", 61, True), ButtonState(1, 2, "ZUG", 61, True),
    ButtonState(1, 3, "DRUCK", 50),       ButtonState(1, 3, "ZUG", 54),
    ButtonState(1, 4, "DRUCK", 55),       ButtonState(1, 4, "ZUG", 57),
    ButtonState(1, 5, "DRUCK", 59),       ButtonState(1, 5, "ZUG", 60),
    ButtonState(1, 6, "DRUCK", 62),       ButtonState(1, 6, "ZUG", 64),
    ButtonState(1, 7, "DRUCK", 67),       ButtonState(1, 7, "ZUG", 66),
    ButtonState(1, 8, "DRUCK", 71),       ButtonState(1, 8, "ZUG", 69),
    ButtonState(1, 9, "DRUCK", 74),       ButtonState(1, 9, "ZUG", 72),
    ButtonState(1, 10, "DRUCK", 79),      ButtonState(1, 10, "ZUG", 76),
    ButtonState(1, 11, "DRUCK", 83),      ButtonState(1, 11, "ZUG", 78),
    ButtonState(1, 12, "DRUCK", 86),      ButtonState(1, 12, "ZUG", 81),

    # Row 2 (C-Dur - Hauptreihe, Knopf 6 = Gleichton G4 = 67)
    ButtonState(2, 1, "DRUCK", 48),       ButtonState(2, 1, "ZUG", 53),
    ButtonState(2, 2, "DRUCK", 52),       ButtonState(2, 2, "ZUG", 55),
    ButtonState(2, 3, "DRUCK", 55),       ButtonState(2, 3, "ZUG", 59),
    ButtonState(2, 4, "DRUCK", 60),       ButtonState(2, 4, "ZUG", 62),
    ButtonState(2, 5, "DRUCK", 64),       ButtonState(2, 5, "ZUG", 65),
    ButtonState(2, 6, "DRUCK", 67),       ButtonState(2, 6, "ZUG", 67),
    ButtonState(2, 7, "DRUCK", 72),       ButtonState(2, 7, "ZUG", 71),
    ButtonState(2, 8, "DRUCK", 76),       ButtonState(2, 8, "ZUG", 74),
    ButtonState(2, 9, "DRUCK", 79),       ButtonState(2, 9, "ZUG", 77),
    ButtonState(2, 10, "DRUCK", 84),      ButtonState(2, 10, "ZUG", 81),
    ButtonState(2, 11, "DRUCK", 88),      ButtonState(2, 11, "ZUG", 83),
    ButtonState(2, 12, "DRUCK", 91),      ButtonState(2, 12, "ZUG", 86),

    # Row 3 (F-Dur - Knopf 6 = Gleichton C5 = 72)
    ButtonState(3, 1, "DRUCK", 53),       ButtonState(3, 1, "ZUG", 58),
    ButtonState(3, 2, "DRUCK", 57),       ButtonState(3, 2, "ZUG", 60),
    ButtonState(3, 3, "DRUCK", 60),       ButtonState(3, 3, "ZUG", 64),
    ButtonState(3, 4, "DRUCK", 65),       ButtonState(3, 4, "ZUG", 67),
    ButtonState(3, 5, "DRUCK", 69),       ButtonState(3, 5, "ZUG", 70),
    ButtonState(3, 6, "DRUCK", 72),       ButtonState(3, 6, "ZUG", 72),
    ButtonState(3, 7, "DRUCK", 77),       ButtonState(3, 7, "ZUG", 76),
    ButtonState(3, 8, "DRUCK", 81),       ButtonState(3, 8, "ZUG", 79),
    ButtonState(3, 9, "DRUCK", 84),       ButtonState(3, 9, "ZUG", 82),
    ButtonState(3, 10, "DRUCK", 89),      ButtonState(3, 10, "ZUG", 86),
    ButtonState(3, 11, "DRUCK", 93),      ButtonState(3, 11, "ZUG", 88),

    # Row 4 (B-Dur / Bb - Knopf 6 = Gleichton F5 = 77)
    ButtonState(4, 1, "DRUCK", 58),       ButtonState(4, 1, "ZUG", 63),
    ButtonState(4, 2, "DRUCK", 62),       ButtonState(4, 2, "ZUG", 65),
    ButtonState(4, 3, "DRUCK", 65),       ButtonState(4, 3, "ZUG", 69),
    ButtonState(4, 4, "DRUCK", 70),       ButtonState(4, 4, "ZUG", 72),
    ButtonState(4, 5, "DRUCK", 74),       ButtonState(4, 5, "ZUG", 75),
    ButtonState(4, 6, "DRUCK", 77),       ButtonState(4, 6, "ZUG", 77),
    ButtonState(4, 7, "DRUCK", 82),       ButtonState(4, 7, "ZUG", 81),
    ButtonState(4, 8, "DRUCK", 86),       ButtonState(4, 8, "ZUG", 84),
    ButtonState(4, 9, "DRUCK", 89),       ButtonState(4, 9, "ZUG", 87),
    ButtonState(4, 10, "DRUCK", 94),      ButtonState(4, 10, "ZUG", 91),
]

PITCH_TO_BUTTONS: dict[int, list[ButtonState]] = {}
for btn in GCFB_BUTTONS:
    PITCH_TO_BUTTONS.setdefault(btn.pitch, []).append(btn)


@dataclass(frozen=True)
class ChordGrip:
    buttons: tuple[ButtonState, ...]  # Sorted by pitch ascending
    direction: str                    # "DRUCK" or "ZUG"

    @property
    def mean_button(self) -> float:
        return sum(b.button for b in self.buttons) / len(self.buttons)

    @property
    def mean_row(self) -> float:
        return sum(b.row for b in self.buttons) / len(self.buttons)


def nearest_valid_pitch(pitch: int) -> int:
    if pitch in PITCH_TO_BUTTONS:
        return pitch
    return min(PITCH_TO_BUTTONS.keys(), key=lambda p: abs(p - pitch))


def generate_chord_candidates(pitches: list[int]) -> list[ChordGrip]:
    """
    Generates all physically playable button combinations for a 1-to-3 note chord:
      - Hard Constraint 1: All buttons must share the same bellows direction (DRUCK or ZUG)
      - Hard Constraint 2: Distinct physical buttons (row, button)
      - Hard Constraint 3: Hand span <= 5 buttons
    """
    norm_pitches = sorted({nearest_valid_pitch(p) for p in pitches})
    valid_grips: list[ChordGrip] = []

    for direction in ("DRUCK", "ZUG"):
        per_pitch_options = [
            [b for b in PITCH_TO_BUTTONS[p] if b.direction == direction]
            for p in norm_pitches
        ]
        if any(len(opts) == 0 for opts in per_pitch_options):
            continue
        for combo in product(*per_pitch_options):
            coords = {(b.row, b.button) for b in combo}
            if len(coords) != len(combo):
                continue
            btn_indices = [b.button for b in combo]
            if max(btn_indices) - min(btn_indices) <= 5:
                valid_grips.append(ChordGrip(buttons=tuple(combo), direction=direction))

    # Fallback to top melody note if a noisy interval cannot be played in one direction
    if not valid_grips and norm_pitches:
        top_p = norm_pitches[-1]
        for b in PITCH_TO_BUTTONS[top_p]:
            valid_grips.append(ChordGrip(buttons=(b,), direction=b.direction))

    return valid_grips


def staff_step_to_musicxml_pitch(staff_step: int) -> tuple[str, int]:
    diatonic_steps = ["C", "D", "E", "F", "G", "A", "B"]
    abs_index = 34 + staff_step  # 34 = B4 (middle line)
    octave = abs_index // 7
    step = diatonic_steps[abs_index % 7]
    return step, octave


def midi_to_musicxml_pitch(midi_pitch: int) -> tuple[str, int, int]:
    octave = (midi_pitch // 12) - 1
    pc = midi_pitch % 12
    mapping = {
        0: ("C", 0),
        1: ("C", 1),
        2: ("D", 0),
        3: ("E", -1),
        4: ("E", 0),
        5: ("F", 0),
        6: ("F", 1),
        7: ("G", 0),
        8: ("A", -1),
        9: ("A", 0),
        10: ("B", -1),
        11: ("B", 0),
    }
    step, alter = mapping[pc]
    return step, alter, octave


def viterbi_optimize_griffschrift(events: list[dict]) -> list[ChordGrip]:
    """
    Finds the globally optimal sequence of ChordGrip states across the piece
    using Dynamic Programming (Viterbi algorithm on a Trellis DAG).
    """
    n = len(events)
    if n == 0:
        return []

    candidates_per_step = [generate_chord_candidates(ev["pitches"]) for ev in events]

    def node_cost(grip: ChordGrip, bass_hint: str | None) -> float:
        cost = 0.0
        # Bass/Harmony Oracle: reward matching bellows direction
        if bass_hint and grip.direction != bass_hint:
            cost += 25.0
        # Same-row bonus for 2-voice chords (Steirischer Standardgriff!)
        rows = {b.row for b in grip.buttons}
        if len(grip.buttons) >= 2:
            if len(rows) == 1:
                cost += 0.0  # Ideal ergonomic grip in one row!
            elif max(rows) - min(rows) == 1:
                cost += 4.0
            else:
                cost += 15.0
        # Prefer main rows (2 and 3)
        for b in grip.buttons:
            if b.row in (1, 4):
                cost += 1.5
            if b.is_semitone:
                cost += 8.0
        return cost

    def edge_cost(prev_g: ChordGrip, curr_g: ChordGrip, is_barline: bool) -> float:
        cost = 0.0
        if prev_g.direction != curr_g.direction:
            cost += 2.5 if is_barline else 18.0
        delta_b = abs(curr_g.mean_button - prev_g.mean_button)
        if delta_b > 1.0:
            cost += 1.2 * ((delta_b - 1.0) ** 2)
        delta_r = abs(curr_g.mean_row - prev_g.mean_row)
        if delta_r > 0:
            cost += 3.0 * delta_r
        return cost

    dp: list[list[float]] = []
    backptr: list[list[int]] = []

    dp.append([node_cost(g, events[0].get("bass_dir_hint")) for g in candidates_per_step[0]])
    backptr.append([-1 for _ in candidates_per_step[0]])

    for t in range(1, n):
        is_barline = events[t]["measure"] != events[t - 1]["measure"]
        bass_hint = events[t].get("bass_dir_hint")
        curr_cands = candidates_per_step[t]
        prev_cands = candidates_per_step[t - 1]
        curr_dp = []
        curr_bp = []
        for c_curr in curr_cands:
            best_val = math.inf
            best_j = 0
            n_cost = node_cost(c_curr, bass_hint)
            for j, c_prev in enumerate(prev_cands):
                val = dp[t - 1][j] + n_cost + edge_cost(c_prev, c_curr, is_barline)
                if val < best_val:
                    best_val = val
                    best_j = j
            curr_dp.append(best_val)
            curr_bp.append(best_j)
        dp.append(curr_dp)
        backptr.append(curr_bp)

    best_last = int(min(range(len(dp[-1])), key=lambda k: dp[-1][k]))
    optimal_path = [None] * n
    idx = best_last
    for t in range(n - 1, -1, -1):
        optimal_path[t] = candidates_per_step[t][idx]
        idx = backptr[t][idx]

    return optimal_path


def quantize_polyphonic_to_grid(
    diskant_notes: list[dict],
    bass_notes: list[dict],
    bpm: float,
    tuning_offset: int,
    max_measures: int = 8,
) -> list[dict]:
    """
    Quantizes continuous Diskant & Bass note events into a 3/4 measure grid
    with up to 2 simultaneous Diskant voices (Zweiklänge) and Bass bellows-direction oracle.
    """
    if not diskant_notes:
        return []
    first_onset = min(n["start_s"] for n in diskant_notes)
    beat_dur_s = 60.0 / bpm
    eighth_dur_s = beat_dur_s / 2.0
    slots_per_measure = 6  # 3/4 Waltz/Landler time signature

    events = []
    for slot in range(max_measures * slots_per_measure):
        t_start = first_onset + slot * eighth_dur_s
        t_end = t_start + eighth_dur_s
        t_mid = 0.5 * (t_start + t_end)

        active_d = [
            n
            for n in diskant_notes
            if n["start_s"] <= t_mid <= n["end_s"] or (t_start <= n["start_s"] < t_end)
        ]
        if not active_d:
            continue

        # Sort by amplitude descending and take up to 2 strongest distinct pitches (Zweiklang)
        active_d.sort(key=lambda n: n["amplitude"], reverse=True)
        chosen_pitches = []
        for n in active_d:
            p = nearest_valid_pitch(n["pitch"] - tuning_offset)
            if p not in chosen_pitches:
                chosen_pitches.append(p)
            if len(chosen_pitches) == 2:
                break
        chosen_pitches.sort()

        # Check Bass Oracle in a ±0.6s window around this beat
        active_b = [
            b for b in bass_notes if (t_start - 0.5) <= b["start_s"] <= (t_end + 0.5)
        ]
        bass_pcs = {(b["pitch"] - tuning_offset) % 12 for b in active_b}
        # In Row 2 (C-Dur): C (0) + E (4) indicates DRUCK; D (2) or H (11) indicates ZUG
        bass_dir_hint = None
        if 0 in bass_pcs or 4 in bass_pcs:
            bass_dir_hint = "DRUCK"
        elif 2 in bass_pcs or 11 in bass_pcs:
            bass_dir_hint = "ZUG"

        measure_idx = (slot // slots_per_measure) + 1
        slot_in_measure = slot % slots_per_measure

        # Merge identical consecutive eighth-note chords on beat boundaries into quarter notes
        if (
            events
            and events[-1]["measure"] == measure_idx
            and events[-1]["pitches"] == chosen_pitches
            and events[-1]["duration_eighths"] == 1
            and (slot_in_measure % 2 == 1)
        ):
            events[-1]["duration_eighths"] = 2
        else:
            events.append(
                {
                    "measure": measure_idx,
                    "slot": slot_in_measure,
                    "duration_eighths": 1,
                    "pitches": chosen_pitches,
                    "bass_dir_hint": bass_dir_hint,
                }
            )
    return events


def build_dual_musicxml(events: list[dict], griff_states: list[ChordGrip], title: str) -> str:
    measures: dict[int, list[tuple[dict, ChordGrip]]] = {}
    for ev, gs in zip(events, griff_states):
        measures.setdefault(ev["measure"], []).append((ev, gs))

    max_m = max(measures.keys()) if measures else 1

    def render_part_measures(is_griffschrift: bool) -> str:
        out = []
        in_druck_bracket = False
        for m in range(1, max_m + 1):
            out.append(f'    <measure number="{m}">')
            if m == 1:
                part_clef = "<clef><sign>G</sign><line>2</line></clef>"
                out.append(
                    f"""      <attributes>
        <divisions>2</divisions>
        <key><fifths>0</fifths></key>
        <time><beats>3</beats><beat-type>4</beat-type></time>
        {part_clef}
      </attributes>"""
                )
            m_items = measures.get(m, [])
            used_eighths = 0
            for idx_in_m, (ev, gs) in enumerate(m_items):
                dur = ev["duration_eighths"]
                used_eighths += dur
                n_type = "quarter" if dur == 2 else "eighth"

                # Handle Druckbalken (solid bracket below staff) in Griffschrift
                if is_griffschrift:
                    if gs.direction == "DRUCK" and not in_druck_bracket:
                        out.append(
                            """      <direction placement="below">
        <direction-type>
          <bracket type="start" number="1" line-end="none" line-type="solid" default-y="-65"/>
        </direction-type>
      </direction>"""
                        )
                        in_druck_bracket = True
                    elif gs.direction == "ZUG" and in_druck_bracket:
                        out.append(
                            """      <direction placement="below">
        <direction-type>
          <bracket type="stop" number="1" line-end="none"/>
        </direction-type>
      </direction>"""
                        )
                        in_druck_bracket = False

                if is_griffschrift:
                    for b_idx, btn in enumerate(gs.buttons):
                        out.append("      <note>")
                        if b_idx > 0:
                            out.append("        <chord/>")
                        step, octave = staff_step_to_musicxml_pitch(btn.staff_step)
                        out.append(f"        <pitch><step>{step}</step><octave>{octave}</octave></pitch>")
                        out.append(f"        <duration>{dur}</duration>")
                        out.append(f"        <type>{n_type}</type>")
                        if btn.is_semitone:
                            out.append("        <accidental>sharp</accidental>")
                        if btn.notehead == "x":
                            out.append("        <notehead>x</notehead>")
                        if b_idx == 0 and idx_in_m == 0:
                            # Show Bass letter B (Grundbass 2. Reihe) on Beat 1
                            bass_txt = "B (Druck)" if gs.direction == "DRUCK" else "B (Zug)"
                            out.append(
                                f'        <lyric number="1"><syllabic>single</syllabic><text>{bass_txt}</text></lyric>'
                            )
                        out.append("      </note>")
                else:
                    for p_idx, pitch in enumerate(ev["pitches"]):
                        out.append("      <note>")
                        if p_idx > 0:
                            out.append("        <chord/>")
                        step, alter, octave = midi_to_musicxml_pitch(pitch)
                        alter_xml = f"<alter>{alter}</alter>" if alter != 0 else ""
                        out.append(
                            f"        <pitch><step>{step}</step>{alter_xml}<octave>{octave}</octave></pitch>"
                        )
                        out.append(f"        <duration>{dur}</duration>")
                        out.append(f"        <type>{n_type}</type>")
                        if alter == 1:
                            out.append("        <accidental>sharp</accidental>")
                        elif alter == -1:
                            out.append("        <accidental>flat</accidental>")
                        out.append("      </note>")

            rem = 6 - used_eighths
            while rem > 0:
                step_dur = 2 if rem >= 2 else 1
                r_type = "quarter" if step_dur == 2 else "eighth"
                out.append(
                    f"      <note><rest/><duration>{step_dur}</duration><type>{r_type}</type></note>"
                )
                rem -= step_dur

            if m == max_m and is_griffschrift and in_druck_bracket:
                out.append(
                    """      <direction placement="below">
        <direction-type>
          <bracket type="stop" number="1" line-end="none"/>
        </direction-type>
      </direction>"""
                )
                in_druck_bracket = False

            out.append("    </measure>")
        return "\n".join(out)

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 4.0 Partwise//EN" "http://www.musicxml.org/dtds/partwise.dtd">
<score-partwise version="4.0">
  <work><work-title>{title}</work-title></work>
  <part-list>
    <score-part id="P1"><part-name>Normalnoten</part-name></score-part>
    <score-part id="P2"><part-name>Griffschrift</part-name></score-part>
  </part-list>
  <part id="P1">
{render_part_measures(is_griffschrift=False)}
  </part>
  <part id="P2">
{render_part_measures(is_griffschrift=True)}
  </part>
</score-partwise>
"""


def main():
    output_dir = Path("outputs")
    analysis_path = output_dir / "01_transcription_analysis.json"
    data = json.loads(analysis_path.read_text(encoding="utf-8"))

    bpm = data["estimated_bpm"]
    tuning_offset = data["best_tuning_offset_from_gcfb"]
    best_tuning = data["best_tuning"]
    diskant_notes = data["diskant_notes"]
    bass_notes = data["bass_notes"]

    print(f"[1/3] Quantizing polyphonic Diskant & Bass (BPM={bpm}, Tuning={best_tuning})...")
    events = quantize_polyphonic_to_grid(
        diskant_notes, bass_notes, bpm=bpm, tuning_offset=tuning_offset, max_measures=8
    )
    print(f"      -> Quantized {len(events)} chord/note events across 8 measures.")

    print("[2/3] Running Viterbi Griffschrift Optimizer (DAG Shortest Path)...")
    griff_states = viterbi_optimize_griffschrift(events)
    for ev, gs in list(zip(events, griff_states))[:12]:
        btns_str = " + ".join(f"R{b.row}.K{b.button}(step={b.staff_step:+d})" for b in gs.buttons)
        print(
            f"      Takt {ev['measure']} | MIDI {str(ev['pitches']):10s} | "
            f"{gs.direction:5s} -> {btns_str}"
        )

    print("[3/3] Generating Dual-System MusicXML & Rendering via Verovio...")
    xml_str = build_dual_musicxml(
        events,
        griff_states,
        title=f"Steirische Harmonika – Normalnoten & Griffschrift ({best_tuning})",
    )
    xml_path = output_dir / "02_kombi_noten_griffschrift.musicxml"
    xml_path.write_text(xml_str, encoding="utf-8")

    tk = verovio.toolkit()
    tk.setOptions(
        {
            "pageWidth": 2200,
            "pageHeight": 1200,
            "scale": 50,
            "adjustPageHeight": True,
            "footer": "none",
        }
    )
    tk.loadData(xml_str)
    svg_str = tk.renderToSVG(1)
    svg_path = output_dir / "02_sheet_music_page1.svg"
    svg_path.write_text(svg_str, encoding="utf-8")
    print(f"      -> Saved MusicXML to {xml_path}")
    print(f"      -> Rendered SVG via Verovio to {svg_path}")


if __name__ == "__main__":
    main()
