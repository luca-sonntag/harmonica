"""
Step 6: End-to-End Full-Length Pipeline (1:45 Video -> Multi-Page DIN A4 PDF with Rosenzopf Druckbalken + Full Stereo Audio-Diff).
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harmonica_pipeline import (
    build_dual_system_musicxml,
    create_audio_verification_files,
    render_musicxml_to_a4_pdf,
    viterbi_optimize_griffschrift,
)
from harmonica_pipeline.transcribe import (
    extract_skyline_measures,
    transcribe_full_audio_hybrid,
)


def main() -> None:
    audio_path = Path("samples/input_full.wav")
    output_dir = Path("outputs")
    cache_path = output_dir / "06_full_transcription_cache.json"

    print("[1/5] Running Hybrid AI Audio Transcription on full 1:45 recording (samples/input_full.wav)...")
    tx_data = transcribe_full_audio_hybrid(audio_path, cache_path=cache_path)

    print("[2/5] Extracting Regularized Downbeat Grid & Skyline 2-Voice Polka Measures...")
    combined_bass = tx_data["bp_bass"] + tx_data["pti_bass"] + tx_data["mu_bass"]
    events, reg_dbs = extract_skyline_measures(
        bp_diskant=tx_data["bp_diskant"],
        mu_diskant=tx_data["mu_diskant"],
        pti_diskant=tx_data["pti_diskant"],
        bass_notes=combined_bass,
        raw_downbeats_s=tx_data["downbeats_s"],
        audio_duration_s=tx_data["duration_s"],
    )
    max_m = max((ev["measure"] for ev in events), default=1)
    print(f"      -> Extracted {len(events)} quantized chord events across {max_m} measures ({reg_dbs[0]:.2f}s .. {reg_dbs[-1]:.2f}s)")

    print("[3/5] Running Global Viterbi Griffschrift Optimizer across all measures...")
    griff_states = viterbi_optimize_griffschrift(events)

    druck_bars = len({ev["measure"] for ev, gs in zip(events, griff_states) if gs.direction == "DRUCK"})
    zug_bars = max_m - druck_bars
    print(f"      -> Bellows balance: {druck_bars} DRUCK bars, {zug_bars} ZUG bars")

    print("[4/5] Generating Dual-System MusicXML & Multi-Page DIN A4 PDF (with Rosenzopf Druckbalken)...")
    xml_str, measure_directions = build_dual_system_musicxml(
        events,
        griff_states,
        title="Steirische Polka (G-C-F-B) – Normalnoten & Griffschrift (System Rosenzopf)",
        emit_musicxml_brackets=False,
    )
    xml_path = output_dir / "06_full_polka_kombi.musicxml"
    xml_path.write_text(xml_str, encoding="utf-8")

    pdf_path = output_dir / "06_full_polka_griffschrift_a4.pdf"
    png_pages = render_musicxml_to_a4_pdf(
        xml_str=xml_str,
        measure_directions=measure_directions,
        output_pdf_path=pdf_path,
        output_dir=output_dir,
        prefix="06_full_polka",
        dpi=300,
    )
    pdf_kb = round(pdf_path.stat().st_size / 1024.0, 1)
    print(f"      -> Saved Multi-Page DIN A4 PDF ({len(png_pages)} pages, {pdf_kb} KB): {pdf_path}")
    for p in png_pages:
        print(f"         * Page Preview: {p}")

    print("[5/5] Generating Full-Length (1:45) Harmonika Synthesizer & Stereo Audio-Diff WAVs...")
    solo_wav = output_dir / "06_full_synthesized_score_only.wav"
    stereo_wav = output_dir / "06_full_stereo_overlay_check.wav"
    create_audio_verification_files(
        orig_wav_path=audio_path,
        events=events,
        griff_states=griff_states,
        downbeats_s=reg_dbs,
        solo_wav_path=solo_wav,
        stereo_wav_path=stereo_wav,
    )
    print(f"      -> Saved Full Solo Score WAV:   {solo_wav}")
    print(f"      -> Saved Full Stereo Diff WAV:  {stereo_wav}")


if __name__ == "__main__":
    main()
