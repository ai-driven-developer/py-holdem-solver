"""Tests for range_parser.py — Poker range notation parsing."""

import pytest
from poker_solver.card import Card, parse_cards
from poker_solver.range_parser import (
    _pair_combos, _suited_combos, _offsuit_combos, _all_combos,
    _parse_token, parse_range, hand_to_str,
)


# ── Combo counts ──


def test_pair_combos_count():
    # C(4,2) = 6 combos for any pocket pair
    assert len(_pair_combos(12)) == 6  # AA
    assert len(_pair_combos(0)) == 6   # 22


def test_suited_combos_count():
    # 4 suits = 4 suited combos
    assert len(_suited_combos(12, 11)) == 4  # AKs


def test_offsuit_combos_count():
    # 4*3 = 12 offsuit combos
    assert len(_offsuit_combos(12, 11)) == 12  # AKo


def test_all_combos_count():
    # 4 + 12 = 16
    assert len(_all_combos(12, 11)) == 16  # AK


# ── Combo properties ──


def test_pair_combos_all_same_rank():
    combos = _pair_combos(12)  # AA
    for c1_id, c2_id in combos:
        assert c1_id // 4 == 12
        assert c2_id // 4 == 12


def test_suited_combos_same_suit():
    combos = _suited_combos(12, 11)  # AKs
    for c1_id, c2_id in combos:
        assert c1_id % 4 == c2_id % 4  # same suit


def test_offsuit_combos_different_suit():
    combos = _offsuit_combos(12, 11)  # AKo
    for c1_id, c2_id in combos:
        assert c1_id % 4 != c2_id % 4  # different suits


def test_pair_combos_unique():
    combos = _pair_combos(10)  # QQ
    keys = {(min(a, b), max(a, b)) for a, b in combos}
    assert len(keys) == 6


# ── _parse_token ──


def test_parse_token_pocket_pair():
    combos = _parse_token("AA")
    assert len(combos) == 6


def test_parse_token_suited_hand():
    combos = _parse_token("AKs")
    assert len(combos) == 4


def test_parse_token_offsuit_hand():
    combos = _parse_token("AKo")
    assert len(combos) == 12


def test_parse_token_all_combos():
    combos = _parse_token("AK")
    assert len(combos) == 16


def test_parse_token_pair_plus():
    # JJ+ = JJ, QQ, KK, AA = 4 pairs * 6 combos
    combos = _parse_token("JJ+")
    assert len(combos) == 4 * 6


def test_parse_token_pair_range():
    # JJ-99 = JJ, TT, 99 = 3 * 6
    combos = _parse_token("JJ-99")
    assert len(combos) == 3 * 6


def test_parse_token_suited_plus():
    # ATs+ = ATs, AJs, AQs, AKs = 4 * 4
    combos = _parse_token("ATs+")
    assert len(combos) == 4 * 4


def test_parse_token_offsuit_plus():
    # ATo+ = ATo, AJo, AQo, AKo = 4 * 12
    combos = _parse_token("ATo+")
    assert len(combos) == 4 * 12


def test_parse_token_suited_range():
    # ATs-A2s = A2s through ATs = 9 * 4
    combos = _parse_token("ATs-A2s")
    assert len(combos) == 9 * 4


def test_parse_token_empty():
    assert _parse_token("") == []
    assert _parse_token("  ") == []


def test_parse_token_22_plus_is_all_pairs():
    # 22+ = all 13 pair ranks
    combos = _parse_token("22+")
    assert len(combos) == 13 * 6


def test_parse_token_aa_plus_is_just_aa():
    combos = _parse_token("AA+")
    assert len(combos) == 6


def test_parse_token_reversed_ranks_normalized():
    # KA should be same as AK
    combos_ak = _parse_token("AK")
    combos_ka = _parse_token("KA")
    assert len(combos_ak) == len(combos_ka)


# ── parse_range ──


def test_parse_range_single_hand():
    hands = parse_range("AA")
    assert len(hands) == 6


def test_parse_range_multiple_hands():
    hands = parse_range("AA,KK")
    assert len(hands) == 12


def test_parse_range_board_collision_filtering():
    board = parse_cards("Ah Kd 7s 3c 2h")
    hands = parse_range("AA", board)
    # AA has 6 combos, but Ah is on the board, removing 3 combos
    assert len(hands) == 3


def test_parse_range_dedup():
    # Parsing same hand twice should deduplicate
    hands = parse_range("AA,AA")
    assert len(hands) == 6


def test_parse_range_complex():
    hands = parse_range("AA,KK,QQ,AKs,AKo")
    # 6 + 6 + 6 + 4 + 12 = 34
    assert len(hands) == 34


def test_parse_range_hands_are_card_tuples():
    hands = parse_range("AA")
    for h in hands:
        assert len(h) == 2
        assert isinstance(h[0], Card)
        assert isinstance(h[1], Card)


def test_parse_range_no_board():
    hands = parse_range("AA", None)
    assert len(hands) == 6


# ── hand_to_str ──


def test_hand_to_str_format():
    hand = (Card("Ah"), Card("Kd"))
    assert hand_to_str(hand) == "AhKd"


def test_hand_to_str_low_cards():
    hand = (Card("2c"), Card("3d"))
    assert hand_to_str(hand) == "2c3d"
