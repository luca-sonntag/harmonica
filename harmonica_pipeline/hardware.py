"""
Hardware Model for a 4-Row Steirische Harmonika (Reference Tuning G-C-F-B)
and Formal Griffschrift Coordinate Math (System Max Rosenzopf).

Critical Domain Invariants:
  1. German 'B' = International 'Bb' (MIDI pitch % 12 == 10, alter = -1).
     German 'H' = International 'B'  (MIDI pitch % 12 == 11, alter = 0).
  2. Mathematical Griffschrift Y-Coordinate (relative to middle line B4 = 0):
       staffStep(row, button) = (row - 2) + 2 * (button - 6)
     - Odd rows (1, 3) -> odd staffStep (always in spaces)
     - Even rows (2, 4) -> even staffStep (always on lines)
     - Rows 1, 2 -> round notehead ('normal')
     - Rows 3, 4 -> cross notehead ('x')
  3. Bass Letters ('A/a', 'B/b', 'C/c', 'D/d') encode Row IDs 1..4, NOT pitches!
"""

from dataclasses import dataclass
from itertools import product


@dataclass(frozen=True)
class ButtonState:
    row: int          # 1..4
    button: int       # 1..12 (6 = Gleichton in rows 2, 3, 4)
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
# Obeys the +5 semitone (fourth) shift between adjacent rows.
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
for _btn in GCFB_BUTTONS:
    PITCH_TO_BUTTONS.setdefault(_btn.pitch, []).append(_btn)

# Bass Row IDs (System Rosenzopf): Row 1..4 -> (Grundbass uppercase, Akkordbass lowercase)
BASS_ROW_LABELS: dict[int, tuple[str, str]] = {
    1: ("A", "a"),
    2: ("B", "b"),
    3: ("C", "c"),
    4: ("D", "d"),
}


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

    @property
    def primary_row(self) -> int:
        """Dominant row for Bass Row-ID assignment (defaults to Row 2 if tied)."""
        counts: dict[int, int] = {}
        for b in self.buttons:
            counts[b.row] = counts.get(b.row, 0) + 1
        return max(counts.keys(), key=lambda r: (counts[r], 1 if r in (2, 3) else 0))


def nearest_valid_pitch(pitch: int) -> int:
    if pitch in PITCH_TO_BUTTONS:
        return pitch
    return min(PITCH_TO_BUTTONS.keys(), key=lambda p: abs(p - pitch))


def generate_chord_candidates(pitches: list[int]) -> list[ChordGrip]:
    """
    Generates all physically playable button combinations for a 1-to-3 note chord:
      - Hard Constraint 1: All buttons must share the exact same bellows direction (DRUCK or ZUG)
      - Hard Constraint 2: Distinct physical buttons (row, button)
      - Hard Constraint 3: Ergonomic hand span (max(button) - min(button) <= 5)
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
    """
    Maps a Griffschrift staffStep (where 0 = 3rd middle line = B4 in G-clef)
    to a pseudo-pitch (step, octave) for standard MusicXML renderers (Verovio/OSMD).
    """
    diatonic_steps = ["C", "D", "E", "F", "G", "A", "B"]
    abs_index = 34 + staff_step  # 34 = 4 * 7 + 6 = B4 (middle line)
    octave = abs_index // 7
    step = diatonic_steps[abs_index % 7]
    return step, octave


def midi_to_musicxml_pitch(midi_pitch: int) -> tuple[str, int, int]:
    """
    Maps an acoustic MIDI pitch (0..127) to international MusicXML (step, alter, octave).
    Note: German 'B' (MIDI % 12 == 10) -> ('B', -1, octave).
          German 'H' (MIDI % 12 == 11) -> ('B',  0, octave).
    """
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
        10: ("B", -1),  # German 'B' (B-flat)
        11: ("B", 0),   # German 'H' (B-natural)
    }
    step, alter = mapping[pc]
    return step, alter, octave


def find_best_transposition(pitches: list[int]) -> tuple[int, float]:
    """
    Finds the optimal semitone shift delta_p in [-6..+6] that maximizes
    playability on the G-C-F-B reference harmonica (especially rows 2 & 3).
    Returns (best_shift_semitones, hit_rate_percent).
    """
    if not pitches:
        return 0, 100.0
    core_pitches = {b.pitch for b in GCFB_BUTTONS if not b.is_semitone and b.row in (2, 3)}
    all_pitches = set(PITCH_TO_BUTTONS.keys())

    best_shift = 0
    best_score = -1.0
    best_hit_rate = 0.0

    for shift in range(-6, 7):
        hits_all = sum(1 for p in pitches if (p + shift) in all_pitches)
        hits_core = sum(1 for p in pitches if (p + shift) in core_pitches)
        hit_rate = 100.0 * hits_all / len(pitches)
        core_rate = 100.0 * hits_core / len(pitches)
        # Prefer shift=0 on ties
        score = 0.7 * hit_rate + 0.3 * core_rate - 0.05 * abs(shift)
        if score > best_score:
            best_score = score
            best_shift = shift
            best_hit_rate = hit_rate

    return best_shift, best_hit_rate
