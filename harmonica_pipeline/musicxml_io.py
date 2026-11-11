"""
Dual-System MusicXML 4.0 Generator (Part 1: Normalnoten, Part 2: Griffschrift).

Enforces Domain Invariants from AGENTS.md and docs/03-griffschrift-spezifikation.md:
  - Part 2 (Griffschrift) always uses <fifths>0</fifths> (no general key signature).
  - Accidentals in Part 2 only appear for physical semitone buttons (is_semitone=True).
  - Noteheads in Part 2: normal for rows 1 & 2, <notehead>x</notehead> for rows 3 & 4.
  - Bass letters (A/a, B/b, C/c, D/d) encode the active row's Grundbass (Beat 1) and Akkordbass (Beat 2).
  - Bellows direction (DRUCK) is encoded both via MusicXML <bracket> spanners and measure metadata.
"""

from .hardware import (
    BASS_ROW_LABELS,
    ChordGrip,
    midi_to_musicxml_pitch,
    staff_step_to_musicxml_pitch,
)


def build_dual_system_musicxml(
    events: list[dict],
    griff_states: list[ChordGrip],
    title: str = "Steirische Harmonika – Normalnoten & Griffschrift (G-C-F-B)",
    emit_musicxml_brackets: bool = False,
) -> tuple[str, dict[int, str]]:
    """
    Builds a standards-compliant MusicXML 4.0 score with two vertically aligned parts:
      - P1: Standard Notation (Normalnoten)
      - P2: Griffschrift (System Max Rosenzopf)

    Returns (musicxml_string, measure_directions_dict) where measure_directions_dict
    maps measure_number (1..N) -> "DRUCK" | "ZUG".
    """
    measures: dict[int, list[tuple[dict, ChordGrip]]] = {}
    for ev, gs in zip(events, griff_states):
        measures.setdefault(ev["measure"], []).append((ev, gs))

    max_m = max(measures.keys()) if measures else 1
    measure_directions: dict[int, str] = {}
    for m in range(1, max_m + 1):
        m_items = measures.get(m, [])
        measure_directions[m] = m_items[0][1].direction if m_items else "DRUCK"

    def render_part_measures(is_griffschrift: bool) -> str:
        out: list[str] = []
        in_druck_bracket = False

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
            m_dir = measure_directions[m]

            # Emit MusicXML <bracket> start/stop on Griffschrift part for external MusicXML editors
            if is_griffschrift and emit_musicxml_brackets:
                if m_dir == "DRUCK" and not in_druck_bracket:
                    out.append(
                        """      <direction placement="below">
        <direction-type>
          <bracket type="start" number="1" line-end="none" line-type="solid" default-y="-72"/>
        </direction-type>
      </direction>"""
                    )
                    in_druck_bracket = True
                elif m_dir == "ZUG" and in_druck_bracket:
                    out.append(
                        """      <direction placement="below">
        <direction-type>
          <bracket type="stop" number="1" line-end="none"/>
        </direction-type>
      </direction>"""
                    )
                    in_druck_bracket = False

            # Determine active Bass Row ID (B/b for Row 2 C-Dur, C/c for Row 3 F-Dur Trio)
            dom_row = 2
            if m_items:
                target_rows = [ev.get("target_row", gs.primary_row) for ev, gs in m_items]
                if sum(1 for r in target_rows if r == 3) > len(target_rows) // 2:
                    dom_row = 3
            grund_bass_lbl, akk_bass_lbl = BASS_ROW_LABELS.get(dom_row, ("B", "b"))

            used_eighths = 0
            placed_beat1_bass = False
            placed_beat2_bass = False

            for idx_in_m, (ev, gs) in enumerate(m_items):
                dur = ev["duration_eighths"]
                used_eighths += dur
                n_type = "quarter" if dur == 2 else "eighth"

                if is_griffschrift:
                    for b_idx, btn in enumerate(gs.buttons):
                        out.append("      <note>")
                        if b_idx > 0:
                            out.append("        <chord/>")
                        step, octave = staff_step_to_musicxml_pitch(btn.staff_step)
                        out.append(f"        <pitch><step>{step}</step><octave>{octave}</octave></pitch>")
                        out.append(f"        <duration>{dur}</duration>")
                        out.append(f"        <type>{n_type}</type>")
                        if btn.is_semitone:
                            out.append("        <accidental>sharp</accidental>")
                        if btn.notehead == "x":
                            out.append("        <notehead>x</notehead>")

                        # Attach Bass Row-ID letters below first note of Beat 1 and Beat 2
                        if b_idx == 0:
                            if not placed_beat1_bass and ev["slot"] < 2:
                                out.append(
                                    f'        <lyric number="1"><syllabic>single</syllabic><text>{grund_bass_lbl}</text></lyric>'
                                )
                                placed_beat1_bass = True
                            elif not placed_beat2_bass and ev["slot"] >= 2:
                                out.append(
                                    f'        <lyric number="1"><syllabic>single</syllabic><text>{akk_bass_lbl}</text></lyric>'
                                )
                                placed_beat2_bass = True
                        out.append("      </note>")
                else:
                    for p_idx, pitch in enumerate(ev["pitches"]):
                        out.append("      <note>")
                        if p_idx > 0:
                            out.append("        <chord/>")
                        step, alter, octave = midi_to_musicxml_pitch(pitch)
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

            # Fill any remaining eighths in the 2/4 bar with rests
            rem = 4 - used_eighths
            while rem > 0:
                step_dur = 2 if rem >= 2 else 1
                r_type = "quarter" if step_dur == 2 else "eighth"
                out.append(
                    f"      <note><rest/><duration>{step_dur}</duration><type>{r_type}</type></note>"
                )
                rem -= step_dur

            if is_griffschrift and emit_musicxml_brackets and m == max_m and in_druck_bracket:
                out.append(
                    """      <direction placement="below">
        <direction-type>
          <bracket type="stop" number="1" line-end="none"/>
        </direction-type>
      </direction>"""
                )
                in_druck_bracket = False

            out.append("    </measure>")
        return "\n".join(out)

    xml_str = f"""<?xml version="1.0" encoding="UTF-8"?>
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
    return xml_str, measure_directions
