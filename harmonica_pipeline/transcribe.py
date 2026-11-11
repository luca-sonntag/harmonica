"""
Hybrid AI Audio Transcription & Skyline Melody/Harmony Extraction Module.

Combines:
  1. JKU Linz 'Beat-This' (Transformer Beat & Downbeat Tracker) + regularized_beats()
  2. Kyutai/Mirelo 'MuScriptor' (MT3 Transformer constrained to instruments=['organ', 'tuba'])
  3. ByteDance 'PianoTranscription' (High-Resolution Onset/Offset CRNN)
  4. Spotify 'Basic Pitch' (via .venv if available) + Tremolo-Merge-Filter (65 ms)
  5. Skyline Melody + Ergonomic Harmony Extractor + Helikon Bass Direction Oracle
"""

import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
import librosa
import numpy as np
import torch

torch.version.cuda = "12.8"  # Align minor tag for torchaudio 2.9.0+cu128 C++ extension check

from beat_this.inference import File2Beats
from muscriptor import NoteEndEvent, NoteStartEvent, TranscriptionModel
from muscriptor.utils.beats import regularized_beats
from piano_transcription_inference import PianoTranscription, sample_rate as pti_sr

from .hardware import nearest_valid_pitch


def apply_tremolo_merge(notes: list[dict], max_gap_s: float = 0.065) -> list[dict]:
    """
    Merges artificial repeated note splits caused by the multi-reed beating
    (Schwebung / Tremolo, ~3..6 Hz -> 40..65 ms amplitude dips) of a Steirische Harmonika.
    """
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


def _run_basic_pitch_subprocess(audio_path: Path, cache_json: Path) -> list[dict]:
    """Runs Spotify Basic Pitch via the dedicated .venv environment if present."""
    venv_py = Path(".venv/Scripts/python.exe")
    if not venv_py.exists():
        return []
    code = (
        "import json; from basic_pitch.inference import predict; "
        f"_, _, events = predict({str(audio_path)!r}, onset_threshold=0.45, frame_threshold=0.30, minimum_note_length=45.0, minimum_frequency=55.0, maximum_frequency=1800.0); "
        "notes = [{'start_s': float(s), 'end_s': float(e), 'pitch': int(p), 'amplitude': float(a)} for s, e, p, a, _ in events]; "
        f"open({str(cache_json)!r}, 'w').write(json.dumps(notes))"
    )
    subprocess.run([str(venv_py), "-c", code], check=True)
    return json.loads(cache_json.read_text(encoding="utf-8"))


def transcribe_full_audio_hybrid(
    audio_path: Path,
    cache_path: Path,
    device: str | None = None,
    force_recompute: bool = False,
) -> dict:
    """
    Runs (or loads from cache) the full-length Hybrid AI Transcription on `audio_path`.
    """
    if cache_path.exists() and not force_recompute:
        print(f"      -> Loading cached full-length AI transcription from {cache_path}")
        return json.loads(cache_path.read_text(encoding="utf-8"))

    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    duration_s = float(librosa.get_duration(path=str(audio_path)))
    print(f"      -> Audio duration: {duration_s:.2f}s | Device: {device}")

    # 1. JKU Linz Beat-This (Neural Beat & Downbeat Tracker)
    t0 = time.perf_counter()
    f2b = File2Beats(checkpoint_path="final0", device=device, dbn=False)
    beats, downbeats = f2b(str(audio_path))
    beats_list = [round(float(b), 4) for b in beats]
    downbeats_list = [round(float(db), 4) for db in downbeats]
    print(
        f"      -> [Beat-This] {len(downbeats_list)} downbeats, {len(beats_list)} beats in {time.perf_counter() - t0:.2f}s"
    )

    # 2. Kyutai/Mirelo MuScriptor (constrained to 'organ' + 'tuba')
    t0 = time.perf_counter()
    mu_model = TranscriptionModel.load_model("small", device=device)
    mu_raw: list[dict] = []
    open_events: dict[int, NoteStartEvent] = {}
    for ev in mu_model.transcribe(audio_path, instruments=["organ", "tuba"]):
        if isinstance(ev, NoteStartEvent):
            open_events[ev.index] = ev
        elif isinstance(ev, NoteEndEvent):
            start_ev = open_events.pop(ev.start_event_index, None)
            if start_ev is not None and ev.end_time > start_ev.start_time:
                mu_raw.append(
                    {
                        "start_s": round(float(start_ev.start_time), 4),
                        "end_s": round(float(ev.end_time), 4),
                        "pitch": int(start_ev.pitch),
                        "instrument": start_ev.instrument,
                        "amplitude": 0.82,
                    }
                )
    mu_merged = apply_tremolo_merge(mu_raw, max_gap_s=0.045)
    mu_diskant = [n for n in mu_merged if 58 <= n["pitch"] <= 92]
    mu_bass = [n for n in mu_merged if n["pitch"] < 58]
    print(
        f"      -> [MuScriptor organ+tuba] {len(mu_diskant)} diskant, {len(mu_bass)} bass notes in {time.perf_counter() - t0:.2f}s"
    )

    # 3. ByteDance High-Resolution PianoTranscription CRNN
    t0 = time.perf_counter()
    ckpt_dir = Path.home() / "piano_transcription_inference_data"
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    ckpt_path = ckpt_dir / "note_F1=0.9677_pedal_F1=0.9186.pth"
    if not ckpt_path.exists() or ckpt_path.stat().st_size < 160_000_000:
        url = "https://zenodo.org/record/4034264/files/CRNN_note_F1%3D0.9677_pedal_F1%3D0.9186.pth?download=1"
        urllib.request.urlretrieve(url, str(ckpt_path))
    audio_pti, _ = librosa.load(str(audio_path), sr=pti_sr, mono=True)
    transcriptor = PianoTranscription(device=device, checkpoint_path=str(ckpt_path))
    tmp_mid = str(cache_path.parent / "tmp_pti_full.mid")
    res_pti = transcriptor.transcribe(audio_pti, tmp_mid)
    Path(tmp_mid).unlink(missing_ok=True)
    pti_raw = [
        {
            "start_s": round(float(e["onset_time"]), 4),
            "end_s": round(float(e["offset_time"]), 4),
            "pitch": int(e["midi_note"]),
            "amplitude": round(float(e["velocity"]) / 127.0, 4),
        }
        for e in res_pti["est_note_events"]
    ]
    pti_merged = apply_tremolo_merge(pti_raw, max_gap_s=0.065)
    pti_diskant = [n for n in pti_merged if 58 <= n["pitch"] <= 92]
    pti_bass = [n for n in pti_merged if n["pitch"] < 58]
    print(
        f"      -> [ByteDance CRNN] {len(pti_diskant)} diskant, {len(pti_bass)} bass notes in {time.perf_counter() - t0:.2f}s"
    )

    # 4. Spotify Basic Pitch (via .venv subprocess)
    t0 = time.perf_counter()
    tmp_bp_json = cache_path.parent / "tmp_bp_full.json"
    bp_raw = _run_basic_pitch_subprocess(audio_path, tmp_bp_json)
    tmp_bp_json.unlink(missing_ok=True)
    bp_merged = apply_tremolo_merge(bp_raw, max_gap_s=0.065)
    bp_diskant = [n for n in bp_merged if 58 <= n["pitch"] <= 92]
    bp_bass = [n for n in bp_merged if n["pitch"] < 58]
    print(
        f"      -> [Basic Pitch] {len(bp_diskant)} diskant, {len(bp_bass)} bass notes in {time.perf_counter() - t0:.2f}s"
    )

    data = {
        "audio_path": str(audio_path),
        "duration_s": round(duration_s, 3),
        "beats_s": beats_list,
        "downbeats_s": downbeats_list,
        "mu_diskant": mu_diskant,
        "mu_bass": mu_bass,
        "pti_diskant": pti_diskant,
        "pti_bass": pti_bass,
        "bp_diskant": bp_diskant,
        "bp_bass": bp_bass,
    }
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def extract_skyline_measures(
    bp_diskant: list[dict],
    mu_diskant: list[dict],
    pti_diskant: list[dict],
    bass_notes: list[dict],
    raw_downbeats_s: list[float],
    audio_duration_s: float = 105.5,
    max_measures: int | None = None,
) -> tuple[list[dict], list[float]]:
    """
    1. Regularizes the downbeat sequence using muscriptor's regularized_beats()
       so spurious sub-beats are dropped and missing barlines are interpolated.
    2. Applies the Skyline Algorithm (highest active pitch = melody voice + best
       harmonizing lower voice 3..9 semitones below) with MuScriptor onset articulation.
    """
    initial_dbs = np.array(raw_downbeats_s, dtype=float)
    reg_dbs = [round(float(x), 3) for x in regularized_beats(initial_dbs).tolist()]
    if len(reg_dbs) >= 2:
        median_bar = float(np.median(np.diff(reg_dbs)))
        if reg_dbs[-1] + 0.6 * median_bar <= audio_duration_s:
            reg_dbs.append(round(reg_dbs[-1] + median_bar, 3))

    # Suppress high 4th-harmonic reed overtones (> MIDI 81)
    all_diskant = [
        n for n in (bp_diskant + mu_diskant + pti_diskant)
        if 58 <= n["pitch"] <= 81
    ]

    events: list[dict] = []
    num_bars = len(reg_dbs) - 1
    if max_measures is not None:
        num_bars = min(num_bars, max_measures)

    for m_idx in range(num_bars):
        t_start = float(reg_dbs[m_idx])
        t_end = float(reg_dbs[m_idx + 1])
        bar_dur = t_end - t_start
        if bar_dur < 0.40 or bar_dur > 1.80:
            continue

        measure_num = m_idx + 1
        slot_dur = bar_dur / 4.0  # 4 eighth-note slots per 2/4 Polka bar

        # Sliding 8-second window to detect modulation between Row 2 (C-Dur) and Row 3 (F-Dur Trio)
        win_disk = [n for n in all_diskant if (t_start - 4.0) <= n["start_s"] <= (t_end + 4.0)]
        win_bass = [b for b in bass_notes if (t_start - 4.0) <= b["start_s"] <= (t_end + 4.0)]
        bb_dur = sum((n["end_s"] - n["start_s"]) for n in win_disk if (n["pitch"] % 12) == 10)
        h_dur = sum((n["end_s"] - n["start_s"]) for n in win_disk if (n["pitch"] % 12) == 11)
        f_bass_cnt = sum(1 for b in win_bass if (b["pitch"] % 12) == 5)
        d_bass_cnt = sum(1 for b in win_bass if (b["pitch"] % 12) == 2)

        # In F-Dur Trio (Row 3), Bb (pc 10) replaces H (pc 11) and F-bass (pc 5) is tonic
        target_row = 3 if (bb_dur > h_dur or f_bass_cnt > d_bass_cnt + 2) else 2

        # Bass & Harmony Direction Oracle per bar (Row-aware!):
        bar_bass = [b for b in bass_notes if b["start_s"] < t_end and b["end_s"] > t_start]
        bass_pcs = {b["pitch"] % 12 for b in bar_bass}
        bar_disk = [n for n in all_diskant if n["start_s"] < t_end and n["end_s"] > t_start]
        disk_pcs = {n["pitch"] % 12 for n in bar_disk}

        druck_votes = 0.0
        zug_votes = 0.0
        if target_row == 2:
            # Row 2 (C-Dur): DRUCK = C/E/G (0, 4, 7), ZUG = G7 (11, 2, 5, 7)
            if 0 in bass_pcs:
                druck_votes += 2.0
            if 2 in bass_pcs:
                zug_votes += 2.0
            if (5 in disk_pcs) or (11 in disk_pcs) or (2 in disk_pcs):
                zug_votes += 2.5
            if (0 in disk_pcs) and (4 in disk_pcs) and (11 not in disk_pcs) and (5 not in disk_pcs):
                druck_votes += 2.5
        else:
            # Row 3 (F-Dur Trio): DRUCK = F/A/C (5, 9, 0), ZUG = C7 (4, 7, 10, 2)
            if 5 in bass_pcs or 9 in bass_pcs:
                druck_votes += 2.2
            if 7 in bass_pcs or 4 in bass_pcs:
                zug_votes += 2.0
            if (10 in disk_pcs) or (4 in disk_pcs) or (7 in disk_pcs and 5 not in disk_pcs):
                zug_votes += 2.5
            if (5 in disk_pcs or 9 in disk_pcs) and (10 not in disk_pcs) and (4 not in disk_pcs):
                druck_votes += 2.5

        bass_dir_hint = "ZUG" if zug_votes > druck_votes else "DRUCK"

        for slot in range(4):
            s_start = t_start + slot * slot_dur
            s_end = s_start + slot_dur

            active = [
                n for n in all_diskant
                if (min(s_end, n["end_s"]) - max(s_start, n["start_s"])) >= 0.040
            ]
            if not active:
                continue

            pitch_strength: dict[int, float] = {}
            for n in active:
                p = nearest_valid_pitch(n["pitch"])
                overlap = min(s_end, n["end_s"]) - max(s_start, n["start_s"])
                onset_bonus = 1.35 if (s_start - 0.035) <= n["start_s"] < s_end else 1.0
                score = (overlap / slot_dur) * n.get("amplitude", 0.7) * onset_bonus
                pitch_strength[p] = max(pitch_strength.get(p, 0.0), score)

            sorted_pitches_desc = sorted(pitch_strength.keys(), reverse=True)
            melody_pitch = sorted_pitches_desc[0]

            harmony_candidates = [
                p for p in sorted_pitches_desc[1:]
                if 3 <= (melody_pitch - p) <= 9
            ]
            if harmony_candidates:
                harmony_pitch = max(harmony_candidates, key=lambda p: pitch_strength[p])
                chosen_pitches = sorted([harmony_pitch, melody_pitch])
            else:
                chosen_pitches = [melody_pitch]

            has_fresh_onset = any(
                (s_start - 0.03) <= n["start_s"] < (s_end - 0.03)
                and nearest_valid_pitch(n["pitch"]) == melody_pitch
                for n in mu_diskant
            )

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
                        "target_row": target_row,
                    }
                )

    return events, reg_dbs
