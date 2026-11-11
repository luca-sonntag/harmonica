"""
Viterbi / DAG Shortest-Path Optimizer for Griffschrift Translation.

Solves the non-injective Pitch -> (Row, Button, BellowsDirection) mapping globally
over the time axis, considering:
  - Helikon Bass / Harmony Direction Oracle (DRUCK vs. ZUG)
  - Intra-measure bellows consistency (avoiding physical bellows flip mid-bar)
  - Ergonomic double-stops (same-row neighbor buttons on Steirische Harmonika)
  - Hand span & smooth finger voice-leading
"""

import math
from .hardware import ChordGrip, generate_chord_candidates


def viterbi_optimize_griffschrift(events: list[dict]) -> list[ChordGrip]:
    """
    Finds the globally optimal sequence of ChordGrip states across the piece
    using Dynamic Programming (Viterbi algorithm on a Trellis DAG).
    """
    n = len(events)
    if n == 0:
        return []

    candidates_per_step = [generate_chord_candidates(ev["pitches"]) for ev in events]

    def node_cost(grip: ChordGrip, bass_hint: str | None, target_row: int = 2) -> float:
        cost = 0.0
        # 1. Bass/Harmony Oracle: reward matching bellows direction
        if bass_hint and grip.direction != bass_hint:
            cost += 25.0
        # 2. Same-row bonus for 2-voice chords (Steirischer Standardgriff!)
        rows = {b.row for b in grip.buttons}
        if len(grip.buttons) >= 2:
            if len(rows) == 1:
                cost += 0.0  # Ideal ergonomic grip in one row!
            elif max(rows) - min(rows) == 1:
                cost += 4.0
            else:
                cost += 15.0
        # 3. Prefer active section row (Row 2 in C-Dur, Row 3 in F-Dur Trio)
        for b in grip.buttons:
            if b.row != target_row:
                cost += 2.0 * abs(b.row - target_row)
            if b.row in (1, 4):
                cost += 1.5
            if b.is_semitone:
                cost += 8.0
        return cost

    def edge_cost(prev_g: ChordGrip, curr_g: ChordGrip, is_barline: bool) -> float:
        cost = 0.0
        # Bellows switch cost: natural at barlines, strongly penalized mid-bar
        if prev_g.direction != curr_g.direction:
            cost += 2.5 if is_barline else 18.0
        # Finger jump distance along the button axis
        delta_b = abs(curr_g.mean_button - prev_g.mean_button)
        if delta_b > 1.0:
            cost += 1.2 * ((delta_b - 1.0) ** 2)
        # Row jump penalty
        delta_r = abs(curr_g.mean_row - prev_g.mean_row)
        if delta_r > 0:
            cost += 3.0 * delta_r
        return cost

    dp: list[list[float]] = []
    backptr: list[list[int]] = []

    dp.append(
        [
            node_cost(g, events[0].get("bass_dir_hint"), events[0].get("target_row", 2))
            for g in candidates_per_step[0]
        ]
    )
    backptr.append([-1 for _ in candidates_per_step[0]])

    for t in range(1, n):
        is_barline = events[t]["measure"] != events[t - 1]["measure"]
        bass_hint = events[t].get("bass_dir_hint")
        target_row = events[t].get("target_row", 2)
        curr_cands = candidates_per_step[t]
        prev_cands = candidates_per_step[t - 1]
        curr_dp = []
        curr_bp = []
        for c_curr in curr_cands:
            best_val = math.inf
            best_j = 0
            n_cost = node_cost(c_curr, bass_hint, target_row)
            for j, c_prev in enumerate(prev_cands):
                val = dp[t - 1][j] + n_cost + edge_cost(c_prev, c_curr, is_barline)
                if val < best_val:
                    best_val = val
                    best_j = j
            curr_dp.append(best_val)
            curr_bp.append(best_j)
        dp.append(curr_dp)
        backptr.append(curr_bp)

    best_last = int(min(range(len(dp[-1])), key=lambda k: dp[-1][k]))
    optimal_path: list[ChordGrip] = [candidates_per_step[0][0]] * n
    idx = best_last
    for t in range(n - 1, -1, -1):
        optimal_path[t] = candidates_per_step[t][idx]
        idx = backptr[t][idx]

    return optimal_path
