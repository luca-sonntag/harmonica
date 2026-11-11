"""
harmonica_pipeline: End-to-End Audio/MusicXML to Steirische Harmonika Griffschrift (System Rosenzopf)
and Dual-System DIN A4 PDF Renderer.
"""

from .hardware import (
    BASS_ROW_LABELS,
    GCFB_BUTTONS,
    PITCH_TO_BUTTONS,
    ButtonState,
    ChordGrip,
    find_best_transposition,
    generate_chord_candidates,
    midi_to_musicxml_pitch,
    nearest_valid_pitch,
    staff_step_to_musicxml_pitch,
)
from .viterbi import viterbi_optimize_griffschrift
from .musicxml_io import build_dual_system_musicxml
from .pdf_renderer import inject_druckbalken_into_verovio_svg, render_musicxml_to_a4_pdf
from .audio_diff import create_audio_verification_files, synthesize_harmonika_chord

__all__ = [
    "BASS_ROW_LABELS",
    "GCFB_BUTTONS",
    "PITCH_TO_BUTTONS",
    "ButtonState",
    "ChordGrip",
    "build_dual_system_musicxml",
    "create_audio_verification_files",
    "find_best_transposition",
    "generate_chord_candidates",
    "inject_druckbalken_into_verovio_svg",
    "midi_to_musicxml_pitch",
    "nearest_valid_pitch",
    "render_musicxml_to_a4_pdf",
    "staff_step_to_musicxml_pitch",
    "synthesize_harmonika_chord",
    "viterbi_optimize_griffschrift",
]
