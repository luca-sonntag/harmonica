"""
Step 4: Hybrid AI Pipeline (JKU 'Beat-This' Downbeats + Basic Pitch Diskant + ByteDance Bass + Viterbi)
Uses JKU Linz 'Beat-This' Downbeats as exact 2/4 Polka measure boundaries, eliminating tempo drift,
and renders the resulting Dual-System Sheet Music (Normalnoten + Griffschrift) via Verovio.
"""

import importlib.util
import json
from pathlib import Path
import verovio
import resvg_py

# Load Viterbi & Hardware model from 02_viterbi_griffschrift_and_render.py
spec = importlib.util.spec_from_file_location(
    "viterbi_mod", Path(__file__).parent / "02_viterbi_griffschrift_and_render.py"
)
vmod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vmod)


def quantize_to_downbeat_measures(
    diskant_notes: list[dict],
    bass_notes: list[dict],
    downbeats_s: list[float],
    max_measures: int = 12,
) -> list[dict]:
    """
    Uses the exact measure downbeats ('Schlag 1') detected by JKU Linz 'Beat-This'
    to subdivide each 2/4 Polka measure [t_m, t_{m+1}] into 4 eighth-note (1/8) slots.
    Because each measure is anchored to the neural downbeat detector, human tempo rubato
    never causes barline drift!
    """
    # Filter out initial pre-roll before the first real phrase (start around 1.78s)
    valid_dbs = [d for d in downbeats_s if d >= 1.5]
    if len(valid_dbs) < 2:
        valid_dbs = downbeats_s

    events = []
    num_bars = min(max_measures, len(valid_dbs) - 1)

    for m_idx in range(num_bars):
        t_bar_start = valid_dbs[m_idx]
        t_bar_end = valid_dbs[m_idx + 1]
        bar_dur = t_bar_end - t_bar_start
        eighth_dur = bar_dur / 4.0  # 2/4 time signature = 4 eighth-note slots per measure
        measure_num = m_idx + 1

        # Determine Measure Bellows Direction Hint from Bass notes within this measure
        bar_bass = [
            b for b in bass_notes
            if (t_bar_start - 0.08) <= b["start_s"] < (t_bar_end - 0.05)
        ]
        # Deep Helikon bass on Beat 1 (MIDI 36/48 = C2/C3 -> DRUCK; MIDI 38/50 = D2/D3 -> ZUG)
        druck_score = sum(2 if b["pitch"] in (36, 48) else 1 for b in bar_bass if (b["pitch"] % 12) in (0, 4))
        zug_score = sum(2 if b["pitch"] in (38, 50) else 1 for b in bar_bass if (b["pitch"] % 12) in (2, 11))
        bass_dir_hint = None
        if druck_score > zug_score:
            bass_dir_hint = "DRUCK"
        elif zug_score > druck_score:
            bass_dir_hint = "ZUG"

        for slot in range(4):
            s_start = t_bar_start + slot * eighth_dur
            s_end = s_start + eighth_dur
            s_mid = 0.5 * (s_start + s_end)

            active_d = [
                n for n in diskant_notes
                if n["start_s"] <= s_mid <= n["end_s"] or (s_start <= n["start_s"] < s_end)
            ]
            if not active_d:
                continue

            active_d.sort(key=lambda n: n["amplitude"], reverse=True)
            chosen_pitches = []
            for n in active_d:
                p = vmod.nearest_valid_pitch(n["pitch"])
                if p not in chosen_pitches:
                    chosen_pitches.append(p)
                if len(chosen_pitches) == 2:
                    break
            chosen_pitches.sort()

            # Merge identical consecutive eighth notes on the same beat (slot 0+1 or slot 2+3) into a quarter note
            if (
                events
                and events[-1]["measure"] == measure_num
                and events[-1]["pitches"] == chosen_pitches
                and events[-1]["duration_eighths"] == 1
                and (slot in (1, 3))
            ):
                events[-1]["duration_eighths"] = 2
            else:
                events.append(
                    {
                        "measure": measure_num,
                        "slot": slot,
                        "duration_eighths": 1,
                        "pitches": chosen_pitches,
                        "bass_dir_hint": bass_dir_hint,
                    }
                )

    return events


def build_polka_2_4_musicxml(events: list[dict], griff_states: list, title: str) -> str:
    measures: dict[int, list[tuple[dict, object]]] = {}
    for ev, gs in zip(events, griff_states):
        measures.setdefault(ev["measure"], []).append((ev, gs))

    max_m = max(measures.keys()) if measures else 1

    def render_part_measures(is_griffschrift: bool) -> str:
        out = []
        for m in range(1, max_m + 1):
            out.append(f'    <measure number="{m}">')
            if m == 1:
                out.append(
                    """      <attributes>
        <divisions>2</divisions>
        <key><fifths>0</fifths></key>
        <time><beats>2</beats><beat-type>4</beat-type></time>
        <clef><sign>G</sign><line>2</line></clef>
      </attributes>"""
                )
            m_items = measures.get(m, [])
            used_eighths = 0
            for idx_in_m, (ev, gs) in enumerate(m_items):
                dur = ev["duration_eighths"]
                used_eighths += dur
                n_type = "quarter" if dur == 2 else "eighth"

                if is_griffschrift:
                    for b_idx, btn in enumerate(gs.buttons):
                        out.append("      <note>")
                        if b_idx > 0:
                            out.append("        <chord/>")
                        step, octave = vmod.staff_step_to_musicxml_pitch(btn.staff_step)
                        out.append(f"        <pitch><step>{step}</step><octave>{octave}</octave></pitch>")
                        out.append(f"        <duration>{dur}</duration>")
                        out.append(f"        <type>{n_type}</type>")
                        if btn.is_semitone:
                            out.append("        <accidental>sharp</accidental>")
                        if btn.notehead == "x":
                            out.append("        <notehead>x</notehead>")
                        if b_idx == 0:
                            # Show Bass pattern (B = Grundbass on Beat 1, b = Akkordbass on Beat 2)
                            # and underline / mark DRUCK vs ZUG
                            if idx_in_m == 0:
                                dir_tag = "[DRUCK] B" if gs.direction == "DRUCK" else "[ZUG] B"
                                out.append(
                                    f'        <lyric number="1"><syllabic>single</syllabic><text>{dir_tag}</text></lyric>'
                                )
                            elif ev["slot"] >= 2 and idx_in_m == 1:
                                out.append(
                                    '        <lyric number="1"><syllabic>single</syllabic><text>b</text></lyric>'
                                )
                        out.append("      </note>")
                else:
                    for p_idx, pitch in enumerate(ev["pitches"]):
                        out.append("      <note>")
                        if p_idx > 0:
                            out.append("        <chord/>")
                        step, alter, octave = vmod.midi_to_musicxml_pitch(pitch)
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

            rem = 4 - used_eighths
            while rem > 0:
                step_dur = 2 if rem >= 2 else 1
                r_type = "quarter" if step_dur == 2 else "eighth"
                out.append(
                    f"      <note><rest/><duration>{step_dur}</duration><type>{r_type}</type></note>"
                )
                rem -= step_dur

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
    bp_data = json.loads((output_dir / "01_transcription_analysis.json").read_text(encoding="utf-8"))
    comp_data = json.loads((output_dir / "03_model_comparison.json").read_text(encoding="utf-8"))

    downbeats_s = comp_data["beat_this"]["downbeats_s"]
    diskant_notes = bp_data["diskant_notes"]
    # Combine MuScriptor (tuba/organ) + Basic Pitch + ByteDance PTI bass notes for rock-solid Zug/Druck oracle
    combined_bass = bp_data["bass_notes"] + comp_data["pti_bass_notes"] + comp_data.get("mu_bass_notes", [])

    print("[1/3] Quantizing onto JKU 'Beat-This' 2/4 Polka Downbeat Grid (12 Measures)...")
    events = quantize_to_downbeat_measures(diskant_notes, combined_bass, downbeats_s, max_measures=12)

    print("[2/3] Running Viterbi Griffschrift Optimizer...")
    griff_states = vmod.viterbi_optimize_griffschrift(events)
    for m in range(1, 13):
        m_evs = [(ev, gs) for ev, gs in zip(events, griff_states) if ev["measure"] == m]
        if m_evs:
            direction = m_evs[0][1].direction
            chords_str = ", ".join(
                "+".join(f"R{b.row}K{b.button}" for b in gs.buttons) for _, gs in m_evs
            )
            print(f"      Takt {m:2d} ({direction:5s}): {chords_str}")

    print("[3/3] Rendering 2/4 Polka Dual-System Sheet Music via Verovio...")
    xml_str = build_polka_2_4_musicxml(
        events,
        griff_states,
        title="Hybrid-Pipeline: Basic Pitch + Beat-This Downbeats + Viterbi (G-C-F-B, 2/4 Polka)",
    )
    xml_path = output_dir / "04_hybrid_polka.musicxml"
    xml_path.write_text(xml_str, encoding="utf-8")

    tk = verovio.toolkit()
    tk.setOptions(
        {
            "pageWidth": 2300,
            "pageHeight": 1300,
            "scale": 48,
            "adjustPageHeight": True,
            "footer": "none",
        }
    )
    tk.loadData(xml_str)
    svg_str = tk.renderToSVG(1)
    svg_path = output_dir / "04_hybrid_polka_sheet.svg"
    svg_path.write_text(svg_str, encoding="utf-8")

    png_bytes = resvg_py.svg_to_bytes(svg_path=str(svg_path), background="white")
    png_path = output_dir / "04_hybrid_polka_sheet.png"
    png_path.write_bytes(png_bytes)
    print(f"      -> Saved {png_path}")


if __name__ == "__main__":
    main()
