"""Parse poker range notation into concrete hand combos.

Supported syntax:
  AA, KK        — pocket pairs (all combos)
  AKs           — suited combos
  AKo           — offsuit combos
  AK            — all combos (suited + offsuit)
  JJ+           — pairs JJ and above (JJ, QQ, KK, AA)
  JJ-99         — pair range (JJ, TT, 99)
  ATs+          — suited hands AT and above (ATs, AJs, AQs, AKs)
  ATo+          — offsuit hands AT and above
  AT+           — all combos AT and above
  ATs-A2s       — suited range
"""

from itertools import combinations
from poker_solver.card import Card, RANK_MAP, RANK_CHARS, SUIT_CHARS

RANKS = list(range(13))  # 0=2 .. 12=A


def _rank_from_char(c: str) -> int:
    return RANK_MAP[c]


def _pair_combos(rank: int) -> list[tuple[int, int]]:
    """All 6 combos for a pocket pair of given rank."""
    suits = [0, 1, 2, 3]
    return [(rank * 4 + s1, rank * 4 + s2)
            for s1, s2 in combinations(suits, 2)]


def _suited_combos(r1: int, r2: int) -> list[tuple[int, int]]:
    """4 suited combos for two different ranks."""
    return [(r1 * 4 + s, r2 * 4 + s) for s in range(4)]


def _offsuit_combos(r1: int, r2: int) -> list[tuple[int, int]]:
    """12 offsuit combos for two different ranks."""
    return [(r1 * 4 + s1, r2 * 4 + s2)
            for s1 in range(4) for s2 in range(4) if s1 != s2]


def _all_combos(r1: int, r2: int) -> list[tuple[int, int]]:
    """All combos for two different ranks (suited + offsuit)."""
    return _suited_combos(r1, r2) + _offsuit_combos(r1, r2)


def _parse_token(token: str) -> list[tuple[int, int]]:
    """Parse a single range token into a list of (card_id1, card_id2) combos."""
    token = token.strip()
    if not token:
        return []

    # Check for range: JJ-99 or ATs-A2s
    if "-" in token:
        parts = token.split("-")
        left, right = parts[0].strip(), parts[1].strip()
        r1_left = _rank_from_char(left[0])
        r2_left = _rank_from_char(left[1])
        r1_right = _rank_from_char(right[0])
        r2_right = _rank_from_char(right[1])

        # Pair range: JJ-99
        if r1_left == r2_left and r1_right == r2_right:
            lo, hi = min(r1_left, r1_right), max(r1_left, r1_right)
            combos = []
            for r in range(lo, hi + 1):
                combos.extend(_pair_combos(r))
            return combos

        # Unpaired range: ATs-A2s
        suffix = ""
        if left[-1] in "so":
            suffix = left[-1]

        # The first rank should be the same
        assert r1_left == r1_right, f"Invalid range: {token}"
        lo = min(r2_left, r2_right)
        hi = max(r2_left, r2_right)
        combos = []
        for r2 in range(lo, hi + 1):
            if r2 == r1_left:
                continue
            high_r, low_r = max(r1_left, r2), min(r1_left, r2)
            if suffix == "s":
                combos.extend(_suited_combos(high_r, low_r))
            elif suffix == "o":
                combos.extend(_offsuit_combos(high_r, low_r))
            else:
                combos.extend(_all_combos(high_r, low_r))
        return combos

    # Check for + suffix
    has_plus = token.endswith("+")
    base = token.rstrip("+")

    r1 = _rank_from_char(base[0])
    r2 = _rank_from_char(base[1])

    suffix = ""
    if len(base) > 2 and base[2] in "so":
        suffix = base[2]

    # Pocket pair
    if r1 == r2:
        if has_plus:
            combos = []
            for r in range(r1, 13):
                combos.extend(_pair_combos(r))
            return combos
        else:
            return _pair_combos(r1)

    # Ensure r1 > r2 (high card first)
    if r1 < r2:
        r1, r2 = r2, r1

    if has_plus:
        # ATs+ means ATs, AJs, AQs, AKs (increase lower rank up to r1-1)
        combos = []
        for r in range(r2, r1):
            if suffix == "s":
                combos.extend(_suited_combos(r1, r))
            elif suffix == "o":
                combos.extend(_offsuit_combos(r1, r))
            else:
                combos.extend(_all_combos(r1, r))
        return combos
    else:
        if suffix == "s":
            return _suited_combos(r1, r2)
        elif suffix == "o":
            return _offsuit_combos(r1, r2)
        else:
            return _all_combos(r1, r2)


def parse_range(range_str: str, board: list[Card] | None = None) -> list[tuple[Card, Card]]:
    """Parse a range string into a list of (Card, Card) combos.

    Excludes combos that conflict with the board cards.
    """
    board_ids = {c.id for c in board} if board else set()
    tokens = [t.strip() for t in range_str.split(",")]

    seen = set()
    result = []
    for token in tokens:
        for c1_id, c2_id in _parse_token(token):
            if c1_id in board_ids or c2_id in board_ids:
                continue
            key = (min(c1_id, c2_id), max(c1_id, c2_id))
            if key not in seen:
                seen.add(key)
                result.append((Card.from_id(key[0]), Card.from_id(key[1])))

    return result


def hand_to_str(hand: tuple[Card, Card]) -> str:
    """Convert a hand combo to a short string like 'AhKd'."""
    return f"{hand[0]}{hand[1]}"
