"""Poker hand evaluator: 7 cards → hand rank (lower is better)."""

from itertools import combinations
from poker_solver.card import Card

# Hand categories (lower = stronger)
STRAIGHT_FLUSH = 0
FOUR_OF_A_KIND = 1
FULL_HOUSE = 2
FLUSH = 3
STRAIGHT = 4
THREE_OF_A_KIND = 5
TWO_PAIR = 6
ONE_PAIR = 7
HIGH_CARD = 8

CATEGORY_NAMES = [
    "Straight Flush", "Four of a Kind", "Full House", "Flush",
    "Straight", "Three of a Kind", "Two Pair", "One Pair", "High Card",
]

# Precomputed straight bitmasks: for each high card (4..12), the 5-bit pattern
_STRAIGHT_MASKS = {(1 << h | 1 << (h-1) | 1 << (h-2) | 1 << (h-3) | 1 << (h-4)): h
                   for h in range(4, 13)}
# Wheel: A-2-3-4-5 (A=12, 2=0, 3=1, 4=2, 5=3)
_STRAIGHT_MASKS[1 << 12 | 1 << 3 | 1 << 2 | 1 << 1 | 1 << 0] = 3


def _eval5(ranks: list[int], suits: list[int]) -> int:
    """Evaluate exactly 5 cards given as ranks and suits.

    Returns a numeric rank where lower = stronger hand.
    Encoding: category * 10_000_000 + kickers
    """
    is_flush = suits[0] == suits[1] == suits[2] == suits[3] == suits[4]

    # Count ranks using a fixed array instead of Counter
    counts = [0] * 13
    for r in ranks:
        counts[r] += 1

    # Check straight via bitmask
    bitmask = 0
    for r in ranks:
        bitmask |= 1 << r
    straight_high = _STRAIGHT_MASKS.get(bitmask, -1)
    is_straight = straight_high >= 0

    # Find quads, trips, pairs by scanning counts desc
    quads = -1
    trips = -1
    pair1 = -1
    pair2 = -1
    for r in range(12, -1, -1):
        c = counts[r]
        if c == 4:
            quads = r
        elif c == 3:
            trips = r
        elif c == 2:
            if pair1 < 0:
                pair1 = r
            else:
                pair2 = r

    if is_straight and is_flush:
        return STRAIGHT_FLUSH * 10_000_000 + straight_high

    if quads >= 0:
        kicker = -1
        for r in range(12, -1, -1):
            if counts[r] > 0 and r != quads:
                kicker = r
                break
        return FOUR_OF_A_KIND * 10_000_000 + quads * 100 + kicker

    if trips >= 0 and pair1 >= 0:
        return FULL_HOUSE * 10_000_000 + trips * 100 + pair1

    if is_flush:
        sr = sorted(ranks, reverse=True)
        val = sr[0] * 50625 + sr[1] * 3375 + sr[2] * 225 + sr[3] * 15 + sr[4]
        return FLUSH * 10_000_000 + val

    if is_straight:
        return STRAIGHT * 10_000_000 + straight_high

    if trips >= 0:
        kickers = []
        for r in range(12, -1, -1):
            if counts[r] > 0 and r != trips:
                kickers.append(r)
                if len(kickers) == 2:
                    break
        return THREE_OF_A_KIND * 10_000_000 + trips * 10000 + kickers[0] * 100 + kickers[1]

    if pair1 >= 0 and pair2 >= 0:
        kicker = -1
        for r in range(12, -1, -1):
            if counts[r] > 0 and r != pair1 and r != pair2:
                kicker = r
                break
        return TWO_PAIR * 10_000_000 + pair1 * 10000 + pair2 * 100 + kicker

    if pair1 >= 0:
        kickers = []
        for r in range(12, -1, -1):
            if counts[r] > 0 and r != pair1:
                kickers.append(r)
                if len(kickers) == 3:
                    break
        return ONE_PAIR * 10_000_000 + pair1 * 3375 + kickers[0] * 225 + kickers[1] * 15 + kickers[2]

    # High card
    sr = sorted(ranks, reverse=True)
    val = sr[0] * 50625 + sr[1] * 3375 + sr[2] * 225 + sr[3] * 15 + sr[4]
    return HIGH_CARD * 10_000_000 + val


# Precompute combo index tuples for C(n,5) where n = 5,6,7
_COMBO_INDICES_BY_N = {
    n: list(combinations(range(n), 5)) for n in (5, 6, 7)
}


def evaluate(hole: tuple[Card, Card], board: list[Card]) -> int:
    """Evaluate the best 5-card hand from 2 hole cards + board cards.

    Returns numeric rank (lower = stronger).
    """
    all_cards = list(hole) + board
    n = len(all_cards)
    all_ranks = [c.rank for c in all_cards]
    all_suits = [c.suit for c in all_cards]
    best = 999_999_999
    for idx in _COMBO_INDICES_BY_N[n]:
        ranks = [all_ranks[i] for i in idx]
        suits = [all_suits[i] for i in idx]
        score = _eval5(ranks, suits)
        if score < best:
            best = score
    return best


def hand_category(rank: int) -> str:
    """Return the name of the hand category for a given rank."""
    cat = rank // 10_000_000
    return CATEGORY_NAMES[cat] if cat < len(CATEGORY_NAMES) else "Unknown"
