"""
Harmonika Synthesizer & Stereo Audio-Diff Verification Generator.

Synthesizes the quantized Dual-System score (Diskant chords + Helikon Grundbass on Beat 1
+ Akkordbass on Beat 2 + subtle Downbeat woodblock tick) and mixes a Stereo Verification WAV:
  - Left Channel:  Original Audio Recording
  - Right Channel: Synthesized Sheet Music
"""

from pathlib import Path
import librosa
import numpy as np
import scipy.io.wavfile as wavfile
from .hardware import ChordGrip


def synthesize_harmonika_chord(
    pitches: list[int], duration_s: float, sr: int = 22050
) -> np.ndarray:
    """
    Synthesizes a warm Steirische Harmonika reed sound (fundamental + 2.5 Hz Schwebung
    + 2nd harmonic) with an attack/release envelope.
    """
    n_samples = max(1, int(duration_s * sr))
    t = np.linspace(0, duration_s, n_samples, endpoint=False)
    wave = np.zeros(n_samples, dtype=np.float32)

    for p in pitches:
        f0 = 440.0 * (2.0 ** ((p - 69.0) / 12.0))
        sig = (
            0.55 * np.sin(2 * np.pi * f0 * t)
            + 0.35 * np.sin(2 * np.pi * (f0 + 2.5) * t)
            + 0.20 * np.sin(2 * np.pi * (2 * f0) * t)
        )
        wave += sig / max(1, len(pitches))

    attack = min(int(0.015 * sr), n_samples // 3)
    release = min(int(0.035 * sr), n_samples // 3)
    env = np.ones(n_samples, dtype=np.float32)
    if attack > 0:
        env[:attack] = np.linspace(0.0, 1.0, attack)
    if release > 0:
        env[-release:] = np.linspace(1.0, 0.05, release)
    return wave * env


def create_audio_verification_files(
    orig_wav_path: Path,
    events: list[dict],
    griff_states: list[ChordGrip],
    downbeats_s: list[float],
    solo_wav_path: Path,
    stereo_wav_path: Path,
) -> None:
    """
    Creates two verification WAV files across the full audio recording:
      1. solo_wav_path:   Only the synthesized notes + Helikon bass from our generated sheet music
      2. stereo_wav_path: Left = Original Audio, Right = Generated Sheet Music + Downbeat Clicks
    """
    orig_y, sr = librosa.load(str(orig_wav_path), sr=22050, mono=True)
    synth_y = np.zeros_like(orig_y)

    # 1. Synthesize each quantized Diskant chord at its exact measure/slot timestamp
    for ev in events:
        i_start = int(ev["start_s"] * sr)
        i_end = min(len(synth_y), int(ev["end_s"] * sr))
        if i_end <= i_start:
            continue
        dur_s = (i_end - i_start) / sr
        chord_wave = synthesize_harmonika_chord(ev["pitches"], dur_s, sr=sr)
        n_s = min(i_end - i_start, len(chord_wave))
        synth_y[i_start : i_start + n_s] += 0.65 * chord_wave[:n_s]

    # 2. Synthesize Bass accompaniment (Beat 1 = Helikon Grundbass, Beat 2 = Akkordbass)
    measures_dir: dict[int, str] = {}
    measures_row: dict[int, int] = {}
    for ev, gs in zip(events, griff_states):
        measures_dir.setdefault(ev["measure"], gs.direction)
        measures_row.setdefault(ev["measure"], ev.get("target_row", 2))

    for m_idx in range(len(downbeats_s) - 1):
        t0, t1 = downbeats_s[m_idx], downbeats_s[m_idx + 1]
        t_mid = 0.5 * (t0 + t1)
        direction = measures_dir.get(m_idx + 1, "DRUCK")
        t_row = measures_row.get(m_idx + 1, 2)
        if t_row == 3:
            # Row 3 (F-Dur Trio): DRUCK = F-Bass (41, 53), ZUG = C-Bass (36, 48)
            bass_pitches = [41, 53] if direction == "DRUCK" else [36, 48]
            akk_pitches = [53, 57] if direction == "DRUCK" else [52, 55]
        else:
            # Row 2 (C-Dur): DRUCK = C-Bass (36, 48), ZUG = G/D-Bass (38, 50)
            bass_pitches = [36, 48] if direction == "DRUCK" else [38, 50]
            akk_pitches = [52, 55] if direction == "DRUCK" else [50, 55]

        # Beat 1: Helikon Grundbass
        i_b1 = int(t0 * sr)
        i_b1_end = min(len(synth_y), int((t0 + 0.25 * (t1 - t0)) * sr))
        if i_b1_end > i_b1:
            bw = synthesize_harmonika_chord(bass_pitches, (i_b1_end - i_b1) / sr, sr=sr)
            n_b1 = min(i_b1_end - i_b1, len(bw))
            synth_y[i_b1 : i_b1 + n_b1] += 0.35 * bw[:n_b1]

        # Beat 2: Akkord-Nachschlag
        i_b2 = int(t_mid * sr)
        i_b2_end = min(len(synth_y), int((t_mid + 0.25 * (t1 - t0)) * sr))
        if i_b2_end > i_b2:
            aw = synthesize_harmonika_chord(akk_pitches, (i_b2_end - i_b2) / sr, sr=sr)
            n_b2 = min(i_b2_end - i_b2, len(aw))
            synth_y[i_b2 : i_b2 + n_b2] += 0.28 * aw[:n_b2]

    # 3. Add a subtle woodblock/metronome tick on each regularized measure Downbeat ("Schlag 1")
    for db in downbeats_s:
        i_db = int(db * sr)
        tick_len = min(int(0.025 * sr), len(synth_y) - i_db)
        if tick_len > 0:
            t_tick = np.linspace(0, tick_len / sr, tick_len, endpoint=False)
            tick = 0.20 * np.sin(2 * np.pi * 1200.0 * t_tick) * np.exp(-t_tick * 120.0)
            synth_y[i_db : i_db + tick_len] += tick

    # Normalize and save solo synth WAV
    synth_norm = np.clip(synth_y / (np.max(np.abs(synth_y)) + 1e-6) * 0.88, -1.0, 1.0)
    solo_wav_path.parent.mkdir(parents=True, exist_ok=True)
    wavfile.write(str(solo_wav_path), sr, (synth_norm * 32767).astype(np.int16))

    # Create Stereo Overlay (Left = Original Audio, Right = Synthesized Sheet Music)
    orig_norm = np.clip(orig_y / (np.max(np.abs(orig_y)) + 1e-6) * 0.85, -1.0, 1.0)
    stereo = np.column_stack([orig_norm, synth_norm])
    wavfile.write(str(stereo_wav_path), sr, (stereo * 32767).astype(np.int16))
