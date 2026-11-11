"""
Unit tests verifying all critical domain invariants from AGENTS.md and docs/.
"""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harmonica_pipeline import (
    BASS_ROW_LABELS,
    GCFB_BUTTONS,
    ButtonState,
    build_dual_system_musicxml,
    find_best_transposition,
    generate_chord_candidates,
    inject_druckbalken_into_verovio_svg,
    midi_to_musicxml_pitch,
    staff_step_to_musicxml_pitch,
    viterbi_optimize_griffschrift,
)


class TestHarmonicaDomainInvariants(unittest.TestCase):
    def test_invariant_1_german_b_vs_h_musicxml_pitch(self):
        """
        Invariant 1:
          - German 'B' (international Bb, pitch % 12 == 10, e.g. MIDI 58, 70) -> ('B', -1, octave)
          - German 'H' (international B,  pitch % 12 == 11, e.g. MIDI 59, 71) -> ('B',  0, octave)
        """
        for midi_b in (58, 70, 82):
            step, alter, _ = midi_to_musicxml_pitch(midi_b)
            self.assertEqual((step, alter), ("B", -1))

        for midi_h in (59, 71, 83):
            step, alter, _ = midi_to_musicxml_pitch(midi_h)
            self.assertEqual((step, alter), ("B", 0))

    def test_invariant_2_global_bellows_direction_and_hand_span(self):
        """
        Invariant 2:
          All simultaneously played notes in a ChordGrip must share the exact same
          bellows direction ('DRUCK' or 'ZUG') and have a hand span <= 5 buttons.
        """
        for chord_pitches in ([60, 64], [59, 65], [67, 71], [67, 72]):
            cands = generate_chord_candidates(chord_pitches)
            self.assertTrue(len(cands) > 0)
            for grip in cands:
                dirs = {b.direction for b in grip.buttons}
                self.assertEqual(len(dirs), 1)
                self.assertIn(grip.direction, ("DRUCK", "ZUG"))
                buttons = [b.button for b in grip.buttons]
                self.assertLessEqual(max(buttons) - min(buttons), 5)

    def test_invariant_3_griffschrift_coordinate_formula_and_noteheads(self):
        """
        Invariant 3:
          staffStep(row, button) = (row - 2) + 2 * (button - 6)
          - Origin staffStep = 0 is Row 2, Button 6 (Gleichton) -> Fake-Pitch B4
          - Odd rows (1, 3) -> odd staffStep (spaces)
          - Even rows (2, 4) -> even staffStep (lines)
          - Rows 1, 2 -> 'normal' notehead; Rows 3, 4 -> 'x' notehead
        """
        r2k6 = ButtonState(2, 6, "DRUCK", 67)
        self.assertEqual(r2k6.staff_step, 0)
        self.assertEqual(staff_step_to_musicxml_pitch(r2k6.staff_step), ("B", 4))

        for btn in GCFB_BUTTONS:
            expected_step = (btn.row - 2) + 2 * (btn.button - 6)
            self.assertEqual(btn.staff_step, expected_step)
            if btn.row in (1, 3):
                self.assertEqual(btn.staff_step % 2, 1)
            else:
                self.assertEqual(btn.staff_step % 2, 0)

            if btn.row in (1, 2):
                self.assertEqual(btn.notehead, "normal")
            else:
                self.assertEqual(btn.notehead, "x")

    def test_hardware_plus_five_semitone_row_shift_and_gleichton(self):
        """
        Checks the +5 semitone (fourth) shift between adjacent rows on buttons 3..10
        and verifies Gleichton on Button 6 for rows 2, 3, 4.
        """
        lookup = {(b.row, b.button, b.direction): b.pitch for b in GCFB_BUTTONS}
        for row in (2, 3, 4):
            self.assertEqual(
                lookup[(row, 6, "DRUCK")],
                lookup[(row, 6, "ZUG")],
                f"Row {row} Button 6 must be Gleichton",
            )
        for row in (1, 2, 3):
            for button in range(3, 11):
                self.assertEqual(
                    lookup[(row + 1, button, "DRUCK")] - lookup[(row, button, "DRUCK")],
                    5,
                )
        for row in (2, 3):
            for button in range(3, 11):
                self.assertEqual(
                    lookup[(row + 1, button, "ZUG")] - lookup[(row, button, "ZUG")],
                    5,
                )

    def test_invariant_4_and_5_musicxml_fifths_and_bass_row_ids(self):
        """
        Invariants 4 & 5:
          - Griffschrift part (P2) always has <fifths>0</fifths>
          - Bass Row IDs map rows 1..4 to A/a, B/b, C/c, D/d
        """
        self.assertEqual(BASS_ROW_LABELS[1], ("A", "a"))
        self.assertEqual(BASS_ROW_LABELS[2], ("B", "b"))
        self.assertEqual(BASS_ROW_LABELS[3], ("C", "c"))
        self.assertEqual(BASS_ROW_LABELS[4], ("D", "d"))

        events = [
            {"measure": 1, "slot": 0, "duration_eighths": 2, "pitches": [67, 72], "bass_dir_hint": "DRUCK"},
            {"measure": 1, "slot": 2, "duration_eighths": 2, "pitches": [67, 72], "bass_dir_hint": "DRUCK"},
            {"measure": 2, "slot": 0, "duration_eighths": 2, "pitches": [59, 65], "bass_dir_hint": "ZUG"},
            {"measure": 2, "slot": 2, "duration_eighths": 2, "pitches": [59, 67], "bass_dir_hint": "ZUG"},
        ]
        grips = viterbi_optimize_griffschrift(events)
        self.assertEqual(grips[0].direction, "DRUCK")
        self.assertEqual(grips[2].direction, "ZUG")

        xml_str, m_dirs = build_dual_system_musicxml(events, grips)
        self.assertIn("<fifths>0</fifths>", xml_str)
        self.assertEqual(m_dirs, {1: "DRUCK", 2: "ZUG"})

    def test_transposition_detector(self):
        c_major_phrase = [60, 62, 64, 65, 67, 69, 71, 72]
        shift, hit_rate = find_best_transposition(c_major_phrase)
        self.assertEqual(shift, 0)
        self.assertEqual(hit_rate, 100.0)


if __name__ == "__main__":
    unittest.main()
