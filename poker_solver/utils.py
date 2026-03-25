"""Shared utility functions for display and formatting."""

from poker_solver.card import Card, RANK_CHARS


def abstract_hand_name(hand: tuple[Card, Card], board: list[Card]) -> str:
    """Convert a concrete hand combo to an abstract name like 'AKs', 'QQ', 'ATo'."""
    r1, r2 = hand[0].rank, hand[1].rank
    s1, s2 = hand[0].suit, hand[1].suit
    high_r, low_r = max(r1, r2), min(r1, r2)
    h = RANK_CHARS[high_r]
    l = RANK_CHARS[low_r]
    if high_r == low_r:
        return f"{h}{l}"
    elif s1 == s2:
        return f"{h}{l}s"
    else:
        return f"{h}{l}o"


def history_label(history: str) -> str:
    """Convert a history string like 'xb67' to a human-readable action sequence."""
    if not history or history == "root":
        return "Root"
    parts = []
    i = 0
    while i < len(history):
        if history[i] == 'x':
            parts.append("Check")
            i += 1
        elif history[i] == 'f':
            parts.append("Fold")
            i += 1
        elif history[i] == 'c':
            parts.append("Call")
            i += 1
        elif history[i] == 'b':
            j = i + 1
            while j < len(history) and (history[j].isdigit() or history[j] == '.'):
                j += 1
            parts.append(f"Bet {history[i+1:j]}")
            i = j
        elif history[i] == 'r':
            j = i + 1
            while j < len(history) and (history[j].isdigit() or history[j] == '.'):
                j += 1
            parts.append(f"Raise {history[i+1:j]}")
            i = j
        elif history[i] == '|':
            parts.append("|")
            i += 1
        else:
            i += 1
    return " -> ".join(parts)
