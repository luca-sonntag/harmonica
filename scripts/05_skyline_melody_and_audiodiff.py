"""
Step 5: Regularized Beat-This Grid + Skyline Melody Extractor + Audio-Diff Verification
Fixes:
  1. Regularizes Beat-This downbeats (removes spurious 0.30s sub-beats like 8.74s and interpolates missing bars).
  2. Skyline Melody Algorithm: Always preserves the highest active Diskant pitch (melody voice)
     plus the best harmonizing 2nd voice (3..9 semitones below), instead of letting loud lower
     drone notes (like Gleichton G4=67) drown out the upper melody!
  3. Synthesizes an Accordion/Harmonika audio track from the generated score and creates a
     Stereo Audio-Diff WAV (Left = Original Recording, Right = Generated Sheet Music) so a
     non-musician can verify the transcription by ear in 5 seconds.
"""

import importlib.util
import json
from pathlib import Path
import numpy as np
import scipy.io.wavfile as wavfile
import librosa
import verovio
import resvg_py
from muscriptor.utils.beats import regularized_beats

# Load Viterbi & Hardware model from 02_viterbi_griffschrift_and_render.py
spec = importlib.util.spec_from_file_location(
    "viterbi_mod", Path(__file__).parent / "02_viterbi_griffschrift_and_render.py"
)
vmod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vmod)


def extract_skyline_measures(
    bp_diskant: list[dict],
    mu_diskant: list[dict],
    bass_notes: list[dict],
    raw_downbeats_s: list[float],
    max_measures: int = 16,
) -> tuple[list[dict], list[float]]:
    """
    1. Regularizes the downbeat sequence using muscriptor's regularized_beats()
       so spurious extra beats (like 8.74s right after 8.44s) are dropped and missing
       downbeats (like 9.22s) are cleanly interpolated.
    2. Uses the Skyline Algorithm (highest pitch = melody voice + harmonizing lower voice)
       combined with MuScriptor's onset articulation.
    """
    # Keep downbeats starting from the first real accompaniment bar (~1.78s)
    initial_dbs = np.array([d for d in raw_downbeats_s if d >= 1.70], dtype=float)
    reg_dbs = regularized_beats(initial_dbs).tolist()
    print(f"      -> Raw Downbeats:         {[round(d, 2) for d in initial_dbs[:12]]}")
    print(f"      -> Regularized Downbeats: {[round(d, 2) for d in reg_dbs[:12]]}")

    # Combine Diskant notes from Basic Pitch (high sensitivity for upper melody 72..76)
    # and MuScriptor (clean articulation)
    all_diskant = bp_diskant + mu_diskant

    events = []
    num_bars = min(max_measures, len(reg_dbs) - 1)

    for m_idx in range(num_bars):
        t_bar_start = reg_dbs[m_idx]
        t_bar_end = reg_dbs[m_idx + 1]
        bar_dur = t_bar_end - t_bar_start
        eighth_dur = bar_dur / 4.0  # 2/4 Polka = 4 eighth-note slots per bar
        measure_num = m_idx + 1

        # Bass Oracle for this measure
        bar_bass = [
            b for b in bass_notes
            if (t_bar_start - 0.08) <= b["start_s"] < (t_bar_end - 0.05)
        ]
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
                n for n in all_diskant
                if n.get("amplitude", 0.8) >= 0.32
                and (
                    (n["start_s"] <= s_mid <= n["end_s"])
                    or (s_start <= n["start_s"] < s_end and (n["end_s"] - n["start_s"]) >= 0.07)
                )
            ]
            if not active_d:
                continue

            # SKYLINE ALGORITHM:
            # 1. Group active detections by normalized Harmonika pitch
            pitch_strength: dict[int, float] = {}
            for n in active_d:
                p = vmod.nearest_valid_pitch(n["pitch"])
                # Give slight priority to notes that newly onset in this slot
                onset_bonus = 1.25 if (s_start - 0.04) <= n["start_s"] < s_end else 1.0
                score = n.get("amplitude", 0.7) * onset_bonus
                pitch_strength[p] = max(pitch_strength.get(p, 0.0), score)

            # 2. Top Melody Voice = highest active pitch (Skyline) with sufficient confidence
            sorted_pitches_desc = sorted(pitch_strength.keys(), reverse=True)
            melody_pitch = sorted_pitches_desc[0]

            # 3. Second Harmony Voice = best lower note within ergonomic interval (3..9 semitones below melody)
            harmony_candidates = [
                p for p in sorted_pitches_desc[1:]
                if 3 <= (melody_pitch - p) <= 9
            ]
            if harmony_candidates:
                harmony_pitch = max(harmony_candidates, key=lambda p: pitch_strength[p])
                chosen_pitches = sorted([harmony_pitch, melody_pitch])
            else:
                chosen_pitches = [melody_pitch]

            # Check if MuScriptor had a fresh re-articulation (onset) in this slot
            has_fresh_onset = any(
                (s_start - 0.03) <= n["start_s"] < (s_end - 0.03)
                and vmod.nearest_valid_pitch(n["pitch"]) == melody_pitch
                for n in mu_diskant
            )

            # Merge into quarter note ONLY if same pitches, within beat 1 (slot 0+1) or beat 2 (slot 2+3),
            # AND there wasn't a clear fresh eighth-note attack
            if (
                events
                and events[-1]["measure"] == measure_num
                and events[-1]["pitches"] == chosen_pitches
                and events[-1]["duration_eighths"] == 1
                and (slot in (1, 3))
                and not has_fresh_onset
            ):
                events[-1]["duration_eighths"] = 2
                events[-1]["end_s"] = s_end
            else:
                events.append(
                    {
                        "measure": measure_num,
                        "slot": slot,
                        "start_s": s_start,
                        "end_s": s_end,
                        "duration_eighths": 1,
                        "pitches": chosen_pitches,
                        "bass_dir_hint": bass_dir_hint,
                    }
                )

    return events, reg_dbs


def synthesize_harmonika_chord(pitches: list[int], duration_s: float, sr: int = 22050) -> np.ndarray:
    """
    Synthesizes a warm Steirische Harmonika reed sound (fundamental + 2nd/3rd harmonics + slight 2.5 Hz Schwebung)
    with a clean envelope so the user can easily hear the transcribed notes.
    """
    n_samples = max(1, int(duration_s * sr))
    t = np.linspace(0, duration_s, n_samples, endpoint=False)
    wave = np.zeros(n_samples, dtype=np.float32)

    for p in pitches:
        f0 = 440.0 * (2.0 ** ((p - 69.0) / 12.0))
        # Reed 1 (f0) + Reed 2 (f0 + 2.5 Hz Schwebung) + 2nd harmonic (2*f0)
        sig = (
            0.55 * np.sin(2 * np.pi * f0 * t)
            + 0.35 * np.sin(2 * np.pi * (f0 + 2.5) * t)
            + 0.20 * np.sin(2 * np.pi * (2 * f0) * t)
        )
        wave += sig / max(1, len(pitches))

    # Attack / Release envelope so each note articulation is clearly audible
    attack = min(int(0.015 * sr), n_samples // 3)
    release = min(int(0.035 * sr), n_samples // 3)
    env = np.ones(n_samples, dtype=np.float32)
    if attack > 0:
        env[:attack] = np.linspace(0.0, 1.0, attack)
    if release > 0:
        env[-release:] = np.linspace(1.0, 0.05, release)
    return wave * env


def create_audio_verification_files(
    orig_wav_path: Path, events: list[dict], downbeats_s: list[float], output_dir: Path
):
    """
    Creates two verification WAV files:
      1. outputs/05_synthesized_score_only.wav (only the notes from our generated sheet music)
      2. outputs/05_stereo_overlay_check.wav (Left = Original Video Audio, Right = Generated Sheet Music + Downbeat Clicks)
    """
    orig_y, sr = librosa.load(str(orig_wav_path), sr=22050, mono=True)
    synth_y = np.zeros_like(orig_y)

    # Synthesize each quantized sheet music chord at its exact measure/slot timestamp
    for ev in events:
        i_start = int(ev["start_s"] * sr)
        i_end = min(len(synth_y), int(ev["end_s"] * sr))
        if i_end <= i_start:
            continue
        dur_s = (i_end - i_start) / sr
        chord_wave = synthesize_harmonika_chord(ev["pitches"], dur_s, sr=sr)
        synth_y[i_start : i_start + len(chord_wave)] += 0.65 * chord_wave[: i_end - i_start]

    # Add a subtle woodblock/metronome tick on each regularized measure Downbeat ("Schlag 1")
    for db in downbeats_s:
        i_db = int(db * sr)
        tick_len = min(int(0.025 * sr), len(synth_y) - i_db)
        if tick_len > 0:
            t_tick = np.linspace(0, tick_len / sr, tick_len, endpoint=False)
            tick = 0.25 * np.sin(2 * np.pi * 1200.0 * t_tick) * np.exp(-t_tick * 120.0)
            synth_y[i_db : i_db + tick_len] += tick

    # Normalize and save solo synth WAV
    synth_norm = np.clip(synth_y / (np.max(np.abs(synth_y)) + 1e-6) * 0.85, -1.0, 1.0)
    solo_path = output_dir / "05_synthesized_score_only.wav"
    wavfile.write(str(solo_path), sr, (synth_norm * 32767).astype(np.int16))

    # Create Stereo Overlay (Left = Original Audio, Right = Synthesized Sheet Music)
    orig_norm = np.clip(orig_y / (np.max(np.abs(orig_y)) + 1e-6) * 0.85, -1.0, 1.0)
    stereo = np.column_stack([orig_norm, synth_norm])
    stereo_path = output_dir / "05_stereo_overlay_check.wav"
    wavfile.write(str(stereo_path), sr, (stereo * 32767).astype(np.int16))

    print(f"      -> Saved Solo Score Audio:   {solo_path}")
    print(f"      -> Saved Stereo Diff Audio:  {stereo_path} (Left=Original, Right=Generated Score)")


def build_clean_polka_musicxml(events: list[dict], griff_states: list, title: str) -> str:
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
                            if idx_in_m == 0:
                                dir_tag = "B (Druck)" if gs.direction == "DRUCK" else "B (Zug)"
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

    raw_downbeats_s = comp_data["beat_this"]["downbeats_s"]
    bp_diskant = bp_data["diskant_notes"]
    mu_diskant = comp_data.get("mu_diskant_notes", [])
    combined_bass = bp_data["bass_notes"] + comp_data["pti_bass_notes"] + comp_data.get("mu_bass_notes", [])

    print("[1/4] Running Regularized Downbeat Grid + Skyline Melody Extractor (16 Measures)...")
    events, reg_dbs = extract_skyline_measures(
        bp_diskant, mu_diskant, combined_bass, raw_downbeats_s, max_measures=16
    )

    print("[2/4] Running Viterbi Griffschrift Optimizer...")
    griff_states = vmod.viterbi_optimize_griffschrift(events)
    for m in range(1, 17):
        m_evs = [(ev, gs) for ev, gs in zip(events, griff_states) if ev["measure"] == m]
        if m_evs:
            direction = m_evs[0][1].direction
            pitches_str = ", ".join(str(ev["pitches"]) for ev, _ in m_evs)
            chords_str = ", ".join(
                "+".join(f"R{b.row}K{b.button}" for b in gs.buttons) for _, gs in m_evs
            )
            print(f"      Takt {m:2d} ({direction:5s}): MIDI {pitches_str:32s} -> {chords_str}")

    print("[3/4] Rendering Skyline Dual-System Sheet Music via Verovio...")
    xml_str = build_clean_polka_musicxml(
        events,
        griff_states,
        title="Skyline-Melodie + Regularized Beat-This + Viterbi (G-C-F-B, 2/4 Polka)",
    )
    xml_path = output_dir / "05_skyline_polka.musicxml"
    xml_path.write_text(xml_str, encoding="utf-8")

    tk = verovio.toolkit()
    tk.setOptions(
        {
            "pageWidth": 2300,
            "pageHeight": 1400,
            "scale": 46,
            "adjustPageHeight": True,
            "footer": "none",
        }
    )
    tk.loadData(xml_str)
    svg_str = tk.renderToSVG(1)
    svg_path = output_dir / "05_skyline_polka_sheet.svg"
    svg_path.write_text(svg_str, encoding="utf-8")

    png_bytes = resvg_py.svg_to_bytes(svg_path=str(svg_path), background="white")
    png_path = output_dir / "05_skyline_polka_sheet.png"
    png_path.write_bytes(png_bytes)
    print(f"      -> Saved {png_path}")

    print("[4/4] Generating Audio-Diff Verification Files (WAV)...")
    create_audio_verification_files(Path("samples/input_30s.wav"), events, reg_dbs[:17], output_dir)


if __name__ == "__main__":
    main()
