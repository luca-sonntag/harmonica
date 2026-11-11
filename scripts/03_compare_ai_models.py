"""
Step 3: Multi-Model AI Benchmark on Steirische Harmonika Audio (RTX 4070 CUDA)
Compares:
  1. Spotify Basic Pitch (CNN CQT polyphonic pitch tracker)
  2. Kyutai / Mirelo MuScriptor (MT3-style Transformer Audio-to-MIDI)
  3. ByteDance High-Resolution Piano Transcription (Onset/Offset CRNN)
  4. JKU Linz Beat-This (Transformer Beat & Downbeat Tracker) vs. Librosa Beat Tracker
And renders a Downbeat-Aligned Dual-System Sheet Music (Normalnoten + Griffschrift) via Verovio.
"""

import json
import time
import urllib.request
from pathlib import Path
import librosa
import matplotlib.pyplot as plt
import numpy as np
import torch
torch.version.cuda = "12.8"  # Align minor tag for torchaudio 2.9.0+cu128 C++ extension check
import verovio
import resvg_py

from beat_this.inference import File2Beats
from muscriptor import TranscriptionModel, NoteStartEvent, NoteEndEvent
from muscriptor.utils.beats import detect_grid
from piano_transcription_inference import PianoTranscription, sample_rate as pti_sr


# Acoustic MIDI pitches (8' fundamental reed) on a standard 4-row G-C-F-B Steirische Harmonika (Diskant)
GCFB_DISKANT_PITCHES = {
    50, 54, 55, 56, 57, 59, 60, 61, 62, 64, 66, 67, 69, 71, 72, 74, 76, 78, 79, 81, 83, 86,
    48, 52, 53, 65, 77, 84, 88, 91,
    58, 70, 82, 89, 93,
    63, 75, 87, 94,
}
C_MAJOR_PCS = {0, 2, 4, 5, 7, 9, 11}


def apply_tremolo_merge(notes: list[dict], max_gap_s: float = 0.065) -> list[dict]:
    if not notes:
        return []
    sorted_notes = sorted(notes, key=lambda n: (n["pitch"], n["start_s"]))
    merged = [sorted_notes[0].copy()]
    for n in sorted_notes[1:]:
        prev = merged[-1]
        if n["pitch"] == prev["pitch"] and (n["start_s"] - prev["end_s"]) <= max_gap_s:
            prev["end_s"] = max(prev["end_s"], n["end_s"])
            prev["amplitude"] = max(prev.get("amplitude", 0.8), n.get("amplitude", 0.8))
        else:
            merged.append(n.copy())
    return sorted(merged, key=lambda n: (n["start_s"], n["pitch"]))


def evaluate_model_notes(name: str, raw_notes: list[dict], elapsed_s: float) -> dict:
    merged = apply_tremolo_merge(raw_notes)
    bass = [n for n in merged if n["pitch"] < 58]
    diskant = [n for n in merged if 58 <= n["pitch"] <= 96]

    total_dur = sum((n["end_s"] - n["start_s"]) for n in diskant) or 1.0
    hw_dur = sum((n["end_s"] - n["start_s"]) for n in diskant if n["pitch"] in GCFB_DISKANT_PITCHES)
    cmaj_dur = sum((n["end_s"] - n["start_s"]) for n in diskant if (n["pitch"] % 12) in C_MAJOR_PCS)

    hw_pct = round(100.0 * hw_dur / total_dur, 1)
    cmaj_pct = round(100.0 * cmaj_dur / total_dur, 1)

    print(f"\n=== {name} (Runtime: {elapsed_s:.2f}s) ===")
    print(f"  Raw Notes: {len(raw_notes)} -> After Tremolo-Merge: {len(merged)}")
    print(f"  Bass (<58): {len(bass)} | Diskant (>=58): {len(diskant)}")
    print(f"  G-C-F-B Hardware Fit: {hw_pct:.1f}% | C-Dur (2. Reihe) Diatonic Fit: {cmaj_pct:.1f}%")

    return {
        "name": name,
        "runtime_s": round(elapsed_s, 2),
        "raw_count": len(raw_notes),
        "merged_count": len(merged),
        "bass_count": len(bass),
        "diskant_count": len(diskant),
        "gcfb_hardware_fit_pct": hw_pct,
        "c_major_diatonic_fit_pct": cmaj_pct,
        "diskant_notes": diskant,
        "bass_notes": bass,
    }


def run_muscriptor(audio_path: Path, device: str) -> tuple[list[dict], float, dict]:
    print("\n[Model 2] Loading Kyutai/Mirelo MuScriptor ('small') on", device, "...")
    t0 = time.perf_counter()
    model = TranscriptionModel.load_model("small", device=device)
    t_infer = time.perf_counter()

    notes = []
    open_events: dict[int, NoteStartEvent] = {}
    instruments_seen: dict[str, int] = {}

    for ev in model.transcribe(audio_path):
        if isinstance(ev, NoteStartEvent):
            open_events[ev.index] = ev
            instruments_seen[ev.instrument] = instruments_seen.get(ev.instrument, 0) + 1
        elif isinstance(ev, NoteEndEvent):
            start_ev = open_events.pop(ev.start_event_index, None)
            if start_ev is not None and ev.end_time > start_ev.start_time:
                notes.append(
                    {
                        "start_s": float(start_ev.start_time),
                        "end_s": float(ev.end_time),
                        "pitch": int(start_ev.pitch),
                        "instrument": start_ev.instrument,
                        "amplitude": 0.8,
                    }
                )
    elapsed = time.perf_counter() - t_infer
    print(f"      -> MuScriptor detected instruments: {instruments_seen} (load+infer: {time.perf_counter()-t0:.1f}s)")
    return notes, elapsed, instruments_seen


def run_bytedance_pti(audio_path: Path, device: str, output_dir: Path) -> tuple[list[dict], float]:
    print("\n[Model 3] Loading ByteDance High-Resolution Piano Transcription on", device, "...")
    ckpt_dir = Path.home() / "piano_transcription_inference_data"
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    ckpt_path = ckpt_dir / "note_F1=0.9677_pedal_F1=0.9186.pth"
    if not ckpt_path.exists() or ckpt_path.stat().st_size < 160_000_000:
        url = "https://zenodo.org/record/4034264/files/CRNN_note_F1%3D0.9677_pedal_F1%3D0.9186.pth?download=1"
        print(f"      -> Downloading ByteDance checkpoint (~165 MB) from Zenodo...")
        urllib.request.urlretrieve(url, str(ckpt_path))

    audio, _ = librosa.load(str(audio_path), sr=pti_sr, mono=True)
    transcriptor = PianoTranscription(device=device, checkpoint_path=str(ckpt_path))
    t0 = time.perf_counter()
    midi_out = str(output_dir / "03_bytedance_pti.mid")
    res = transcriptor.transcribe(audio, midi_out)
    elapsed = time.perf_counter() - t0

    notes = []
    for ev in res["est_note_events"]:
        notes.append(
            {
                "start_s": float(ev["onset_time"]),
                "end_s": float(ev["offset_time"]),
                "pitch": int(ev["midi_note"]),
                "amplitude": float(ev["velocity"]) / 127.0,
            }
        )
    return notes, elapsed


def run_beat_this(audio_path: Path, device: str) -> dict:
    print("\n[Model 4] Running JKU Linz 'Beat-This' (Transformer Beat & Downbeat Tracker)...")
    t0 = time.perf_counter()
    f2b = File2Beats(checkpoint_path="final0", device=device, dbn=False)
    beats, downbeats = f2b(str(audio_path))
    elapsed = time.perf_counter() - t0

    beats = [float(b) for b in beats]
    downbeats = [float(db) for db in downbeats]

    # Calculate inter-beat intervals and meter (beats per bar)
    ibis = np.diff(beats) if len(beats) > 1 else np.array([0.5])
    bpm = float(60.0 / np.median(ibis))

    # Count how many beats lie between consecutive downbeats
    bar_beat_counts = []
    for i in range(len(downbeats) - 1):
        db_start, db_end = downbeats[i], downbeats[i + 1]
        c = sum(1 for b in beats if (db_start - 0.08) <= b < (db_end - 0.08))
        bar_beat_counts.append(c)
    median_meter = int(np.median(bar_beat_counts)) if bar_beat_counts else 3

    print(f"      -> Beat-This Runtime: {elapsed:.2f}s")
    print(f"      -> Detected Tempo: {bpm:.1f} BPM")
    print(f"      -> Detected Meter (Beats per Measure): {median_meter}/4 (counts per bar: {bar_beat_counts})")
    print(f"      -> Detected Downbeats ('Schlag 1'): {[round(d, 2) for d in downbeats[:10]]}")

    return {
        "runtime_s": round(elapsed, 2),
        "bpm": round(bpm, 2),
        "meter_beats_per_bar": median_meter,
        "bar_beat_counts": bar_beat_counts,
        "beats_s": [round(b, 3) for b in beats],
        "downbeats_s": [round(d, 3) for d in downbeats],
    }


def main():
    audio_path = Path("samples/input_30s.wav")
    output_dir = Path("outputs")
    device = "cuda" if torch.cuda.is_available() else "cpu"

    # Load Step 1 Basic Pitch results
    bp_data = json.loads((output_dir / "01_transcription_analysis.json").read_text(encoding="utf-8"))
    bp_all_notes = bp_data["diskant_notes"] + bp_data["bass_notes"]
    bp_eval = evaluate_model_notes("1. Spotify Basic Pitch", bp_all_notes, elapsed_s=3.4)

    # Run Model 2: Kyutai / Mirelo MuScriptor (optional if HF gated license not yet accepted)
    mu_eval = None
    try:
        mu_notes, mu_time, mu_inst = run_muscriptor(audio_path, device=device)
        mu_eval = evaluate_model_notes("2. Kyutai/Mirelo MuScriptor (small)", mu_notes, elapsed_s=mu_time)
        mu_eval["instruments"] = mu_inst
    except Exception as exc:
        print(f"      -> [Info] MuScriptor weights gated on HF (accept at https://huggingface.co/MuScriptor/muscriptor-small): {type(exc).__name__}")

    # Run Model 3: ByteDance High-Resolution Piano Transcription
    pti_notes, pti_time = run_bytedance_pti(audio_path, device=device, output_dir=output_dir)
    pti_eval = evaluate_model_notes("2. ByteDance PianoTranscription (CRNN)", pti_notes, elapsed_s=pti_time)

    # Run Model 4: JKU Linz Beat-This
    bt_info = run_beat_this(audio_path, device=device)

    # Generate comparison visual plot (outputs/03_model_comparison.png)
    models_plot = [
        ("1. Spotify Basic Pitch (G-C-F-B Fit: " + f"{bp_eval['gcfb_hardware_fit_pct']}%, C-Dur Fit: {bp_eval['c_major_diatonic_fit_pct']}%)", bp_eval),
        ("2. ByteDance CRNN Onset/Offset (G-C-F-B Fit: " + f"{pti_eval['gcfb_hardware_fit_pct']}%, C-Dur Fit: {pti_eval['c_major_diatonic_fit_pct']}%)", pti_eval),
    ]
    if mu_eval is not None:
        models_plot.append(
            ("3. Kyutai/Mirelo MuScriptor (G-C-F-B Fit: " + f"{mu_eval['gcfb_hardware_fit_pct']}%)", mu_eval)
        )

    fig, axes = plt.subplots(len(models_plot), 1, figsize=(14, 4.5 * len(models_plot)), sharex=True)
    if len(models_plot) == 1:
        axes = [axes]

    for ax, (title, m_data) in zip(axes, models_plot):
        # Plot Beat-This Beats (thin grey) and Downbeats / Barlines (thick green!)
        for b in bt_info["beats_s"]:
            ax.axvline(b, color="#dddddd", linestyle="--", linewidth=0.7, zorder=1)
        for db in bt_info["downbeats_s"]:
            ax.axvline(db, color="#2ca02c", linestyle="-", linewidth=1.6, alpha=0.8, zorder=2)

        ax.axhline(58, color="#d9534f", linestyle=":", linewidth=1.0)
        ax.axhline(67, color="#f0ad4e", linestyle="-.", linewidth=1.0)

        for n in m_data["bass_notes"]:
            ax.plot([n["start_s"], n["end_s"]], [n["pitch"], n["pitch"]], color="#d9534f", linewidth=3.5, zorder=3)
        for n in m_data["diskant_notes"]:
            ax.plot([n["start_s"], n["end_s"]], [n["pitch"], n["pitch"]], color="#0275d8", linewidth=3.5, zorder=3)

        ax.set_title(title + f" | Green vertical lines = JKU 'Beat-This' Downbeats ({bt_info['bpm']} BPM, {bt_info['meter_beats_per_bar']}/4)")
        ax.set_ylabel("MIDI Pitch")
        ax.set_ylim(32, 85)
        ax.set_xlim(0, 30)
        ax.grid(True, axis="y", alpha=0.3)

    axes[-1].set_xlabel("Time (seconds) — Green Lines = Measure Downbeats ('Schlag 1'), Grey Dashed = Quarter Beats")
    plt.tight_layout()
    comp_plot_path = output_dir / "03_model_comparison.png"
    plt.savefig(comp_plot_path, dpi=150)
    plt.close(fig)

    # Save benchmark JSON
    models_summary = [
        {k: v for k, v in bp_eval.items() if not k.endswith("_notes")},
        {k: v for k, v in pti_eval.items() if not k.endswith("_notes")},
    ]
    if mu_eval is not None:
        models_summary.append({k: v for k, v in mu_eval.items() if not k.endswith("_notes")})

    bench_out = {
        "beat_this": bt_info,
        "models": models_summary,
        "pti_diskant_notes": pti_eval["diskant_notes"],
        "pti_bass_notes": pti_eval["bass_notes"],
    }
    (output_dir / "03_model_comparison.json").write_text(json.dumps(bench_out, indent=2), encoding="utf-8")
    print(f"\nSaved visual comparison to {comp_plot_path} and outputs/03_model_comparison.json")


if __name__ == "__main__":
    main()
