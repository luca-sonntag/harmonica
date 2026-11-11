"""
Step 1: Audio-to-MIDI Transcription & Acoustic Domain Analysis
Tests Spotify's Basic Pitch AI model + Librosa DSP on a real Steirische Harmonika recording.
"""

import json
from pathlib import Path
import numpy as np
import librosa
import matplotlib.pyplot as plt
from basic_pitch.inference import predict
from basic_pitch import ICASSP_2022_MODEL_PATH


# Acoustic MIDI pitches (8' fundamental reed) on a standard 4-row G-C-F-B Steirische Harmonika (Diskant)
# Row 2 Gleichton (Button 6) = MIDI 67 (G4 = 392.0 Hz)
GCFB_DISKANT_PITCHES = {
    # Row 1 (G):
    50, 54, 55, 56, 57, 59, 60, 61, 62, 64, 66, 67, 69, 71, 72, 74, 76, 78, 79, 81, 83, 86,
    # Row 2 (C):
    48, 52, 53, 55, 59, 60, 62, 64, 65, 67, 71, 72, 74, 76, 77, 79, 81, 83, 84, 86, 88, 91,
    # Row 3 (F):
    53, 57, 58, 60, 64, 65, 67, 69, 70, 72, 76, 77, 79, 81, 82, 84, 86, 88, 89, 93,
    # Row 4 (B / Bb):
    58, 62, 63, 65, 69, 70, 72, 74, 75, 77, 81, 82, 84, 86, 87, 89, 91, 94,
}

# Standard Harmonika Tunings and their semitone offset relative to G-C-F-B
TUNINGS = {
    "F-B-Es-As (-2)": -2,
    "Fis-H-E-A (-1)": -1,
    "G-C-F-B (0)": 0,
    "Gis-Cis-Fis-H (+1)": 1,
    "A-D-G-C (+2)": 2,
    "B-Es-As-Des (+3)": 3,
    "H-E-A-D (+4)": 4,
}

NOTE_NAMES_DE = ["C", "Cis", "D", "Es", "E", "F", "Fis", "G", "As", "A", "B", "H"]


def midi_to_name_de(pitch: int) -> str:
    octave = (pitch // 12) - 1
    return f"{NOTE_NAMES_DE[pitch % 12]}{octave}"


def apply_tremolo_merge(notes: list[dict], max_gap_s: float = 0.065) -> list[dict]:
    """
    Merges consecutive notes of the exact same MIDI pitch separated by a tiny gap
    caused by Steirische Harmonika Schwebung (2-3 reed tremolo amplitude modulation).
    """
    if not notes:
        return []
    sorted_notes = sorted(notes, key=lambda n: (n["pitch"], n["start_s"]))
    merged = [sorted_notes[0].copy()]
    for n in sorted_notes[1:]:
        prev = merged[-1]
        if n["pitch"] == prev["pitch"] and (n["start_s"] - prev["end_s"]) <= max_gap_s:
            prev["end_s"] = max(prev["end_s"], n["end_s"])
            prev["amplitude"] = max(prev["amplitude"], n["amplitude"])
        else:
            merged.append(n.copy())
    return sorted(merged, key=lambda n: (n["start_s"], n["pitch"]))


def evaluate_tuning_fit(diskant_notes: list[dict]) -> list[tuple[str, int, float]]:
    """
    Scores how well the detected Diskant notes fit each standard Steirische Harmonika tuning
    (weighted by note duration * amplitude, with slight bonus for main Row 2 / Row 3 diatonic fit).
    """
    results = []
    total_weight = sum((n["end_s"] - n["start_s"]) * n["amplitude"] for n in diskant_notes) or 1.0
    # C-major / F-major diatonic pitch classes in G-C-F-B (main rows 2 and 3)
    main_row_pcs = {0, 2, 4, 5, 7, 9, 10, 11}

    for name, offset in TUNINGS.items():
        valid_pitches = {p + offset for p in GCFB_DISKANT_PITCHES}
        matched_weight = sum(
            (n["end_s"] - n["start_s"]) * n["amplitude"]
            for n in diskant_notes
            if n["pitch"] in valid_pitches
        )
        main_row_weight = sum(
            (n["end_s"] - n["start_s"]) * n["amplitude"]
            for n in diskant_notes
            if ((n["pitch"] - offset) % 12) in main_row_pcs
        )
        hw_pct = 100.0 * matched_weight / total_weight
        main_pct = 100.0 * main_row_weight / total_weight
        # Combined score prioritizes 100% hardware match + playing on main rows (2/3)
        results.append((name, offset, round(0.7 * hw_pct + 0.3 * main_pct, 2), round(hw_pct, 2)))

    return sorted(results, key=lambda x: (x[2], -abs(x[1])), reverse=True)


def main():
    audio_path = Path("samples/input_30s.wav")
    output_dir = Path("outputs")
    output_dir.mkdir(exist_ok=True)

    print(f"[1/4] Running Spotify Basic Pitch on {audio_path}...")
    model_output, midi_data, note_events = predict(
        str(audio_path),
        ICASSP_2022_MODEL_PATH,
        onset_threshold=0.5,
        frame_threshold=0.3,
        minimum_note_length=58.0,  # ms
    )

    raw_midi_path = output_dir / "01_basic_pitch_raw.mid"
    midi_data.write(str(raw_midi_path))

    raw_notes = [
        {
            "start_s": float(start_s),
            "end_s": float(end_s),
            "pitch": int(pitch),
            "note_de": midi_to_name_de(int(pitch)),
            "amplitude": float(amp),
        }
        for start_s, end_s, pitch, amp, _ in note_events
    ]
    raw_notes.sort(key=lambda x: (x["start_s"], x["pitch"]))
    print(f"      -> Raw notes detected by Basic Pitch: {len(raw_notes)}")

    print("[2/4] Running Harmonika Domain Filters (Tremolo-Merge & Helikon-Bass Split)...")
    merged_notes = apply_tremolo_merge(raw_notes, max_gap_s=0.065)
    bass_notes = [n for n in merged_notes if n["pitch"] < 58]
    diskant_notes = [n for n in merged_notes if 58 <= n["pitch"] <= 96]
    print(f"      -> After Tremolo Merge: {len(merged_notes)} notes")
    print(f"      -> Helikon-Bass (< MIDI 58): {len(bass_notes)} notes")
    print(f"      -> Diskant / Melodie (>= MIDI 58): {len(diskant_notes)} notes")

    print("[3/4] Running Librosa Beat-Tracking & Tuning Detection...")
    y, sr = librosa.load(str(audio_path), sr=22050)
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    bpm = float(np.ndim(tempo) and tempo[0] or tempo)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr).tolist()
    print(f"      -> Estimated Tempo: {bpm:.1f} BPM ({len(beat_times)} beats in 30s)")

    # Pitch class histogram (weighted by duration * amplitude)
    pc_weights = np.zeros(12)
    for n in diskant_notes:
        pc_weights[n["pitch"] % 12] += (n["end_s"] - n["start_s"]) * n["amplitude"]
    if pc_weights.sum() > 0:
        pc_weights /= pc_weights.sum()

    tuning_scores = evaluate_tuning_fit(diskant_notes)
    print("\n--- Harmonika Tuning Fit (Diskant Hardware Match) ---")
    for name, offset, combined, hw_pct in tuning_scores:
        print(f"  {name:22s}: {hw_pct:5.1f}% hardware match (Score: {combined:5.1f}%)")

    best_tuning_name, best_offset, best_combined, best_hw_pct = tuning_scores[0]

    # Save structured analysis JSON
    summary = {
        "audio_file": str(audio_path),
        "estimated_bpm": round(bpm, 2),
        "raw_note_count": len(raw_notes),
        "merged_note_count": len(merged_notes),
        "bass_note_count": len(bass_notes),
        "diskant_note_count": len(diskant_notes),
        "best_tuning": best_tuning_name,
        "best_tuning_offset_from_gcfb": best_offset,
        "best_tuning_match_pct": best_hw_pct,
        "beat_times_s": [round(t, 3) for t in beat_times],
        "diskant_notes": diskant_notes,
        "bass_notes": bass_notes,
    }
    json_path = output_dir / "01_transcription_analysis.json"
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("[4/4] Generating Visual Diagnostic Plot (outputs/01_audio_analysis.png)...")
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 8), gridspec_kw={"height_ratios": [2.2, 1]})

    for bt in beat_times:
        ax1.axvline(bt, color="#cccccc", linestyle="--", linewidth=0.7, zorder=1)
    ax1.axhline(58, color="#d9534f", linestyle=":", linewidth=1.2, label="Bass / Diskant Split (MIDI 58)")
    ax1.axhline(67, color="#f0ad4e", linestyle="-.", linewidth=1.2, label="Gleichton 2. Reihe (G4 = MIDI 67)")

    for n in bass_notes:
        ax1.plot(
            [n["start_s"], n["end_s"]],
            [n["pitch"], n["pitch"]],
            color="#d9534f",
            linewidth=4,
            solid_capstyle="butt",
            zorder=3,
        )
    for n in diskant_notes:
        ax1.plot(
            [n["start_s"], n["end_s"]],
            [n["pitch"], n["pitch"]],
            color="#0275d8",
            linewidth=4,
            solid_capstyle="butt",
            zorder=3,
        )

    ax1.set_title(
        f"Basic Pitch + Harmonika Filter (Tempo ≈ {bpm:.1f} BPM | Detected Tuning: {best_tuning_name} @ {best_hw_pct:.1f}% Hardware Match)"
    )
    ax1.set_xlabel("Time (seconds)")
    ax1.set_ylabel("MIDI Pitch (Red = Helikon-Bass, Blue = Diskant)")
    ax1.set_xlim(0, 30)
    ax1.grid(True, axis="y", alpha=0.3)
    ax1.legend(loc="upper right")

    bars = ax2.bar(NOTE_NAMES_DE, pc_weights * 100.0, color="#5cb85c", edgecolor="#2b542c")
    ax2.set_title("Detected Pitch Class Distribution (Deutscher Notenname, gewichtet nach Dauer × Lautstärke)")
    ax2.set_ylabel("Share (%)")
    ax2.grid(True, axis="y", alpha=0.3)
    for bar, pct in zip(bars, pc_weights * 100.0):
        if pct > 1.0:
            ax2.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.5,
                f"{pct:.1f}%",
                ha="center",
                va="bottom",
                fontsize=9,
            )

    plt.tight_layout()
    plot_path = output_dir / "01_audio_analysis.png"
    plt.savefig(plot_path, dpi=150)
    plt.close(fig)
    print(f"Done! Saved {json_path} and {plot_path}")


if __name__ == "__main__":
    main()
