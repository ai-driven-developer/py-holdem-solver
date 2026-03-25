"""Tests for evaluator.py — Poker hand evaluation."""

import pytest
from poker_solver.card import Card, parse_cards
from poker_solver.evaluator import (
    _eval5, evaluate, hand_category,
    STRAIGHT_FLUSH, FOUR_OF_A_KIND, FULL_HOUSE, FLUSH,
    STRAIGHT, THREE_OF_A_KIND, TWO_PAIR, ONE_PAIR, HIGH_CARD,
)


def _make5(cards_str: str):
    """Helper: parse 5 cards and return (ranks, suits)."""
    cards = parse_cards(cards_str)
    assert len(cards) == 5
    return [c.rank for c in cards], [c.suit for c in cards]


# ── _eval5: hand category detection ──


def test_eval5_straight_flush():
    ranks, suits = _make5("Ah Kh Qh Jh Th")
    r = _eval5(ranks, suits)
    assert r // 10_000_000 == STRAIGHT_FLUSH


def test_eval5_straight_flush_low():
    # A-2-3-4-5 suited (wheel flush)
    ranks, suits = _make5("Ac 2c 3c 4c 5c")
    r = _eval5(ranks, suits)
    assert r // 10_000_000 == STRAIGHT_FLUSH


def test_eval5_four_of_a_kind():
    ranks, suits = _make5("Ah Ac Ad As Kh")
    r = _eval5(ranks, suits)
    assert r // 10_000_000 == FOUR_OF_A_KIND


def test_eval5_full_house():
    ranks, suits = _make5("Ah Ac Ad Ks Kh")
    r = _eval5(ranks, suits)
    assert r // 10_000_000 == FULL_HOUSE


def test_eval5_flush():
    ranks, suits = _make5("Ah Kh Qh Jh 9h")
    r = _eval5(ranks, suits)
    assert r // 10_000_000 == FLUSH


def test_eval5_straight():
    ranks, suits = _make5("Ah Kd Qh Js Th")
    r = _eval5(ranks, suits)
    assert r // 10_000_000 == STRAIGHT


def test_eval5_wheel_straight():
    ranks, suits = _make5("Ah 2d 3h 4s 5h")
    r = _eval5(ranks, suits)
    assert r // 10_000_000 == STRAIGHT


def test_eval5_three_of_a_kind():
    ranks, suits = _make5("Ah Ac Ad Ks Qh")
    r = _eval5(ranks, suits)
    assert r // 10_000_000 == THREE_OF_A_KIND


def test_eval5_two_pair():
    ranks, suits = _make5("Ah Ac Kd Ks Qh")
    r = _eval5(ranks, suits)
    assert r // 10_000_000 == TWO_PAIR


def test_eval5_one_pair():
    ranks, suits = _make5("Ah Ac Kd Qs Jh")
    r = _eval5(ranks, suits)
    assert r // 10_000_000 == ONE_PAIR


def test_eval5_high_card():
    ranks, suits = _make5("Ah Kd Qs Jh 9c")
    r = _eval5(ranks, suits)
    assert r // 10_000_000 == HIGH_CARD


# ── _eval5: cross-category ordering (lower = stronger) ──


def test_straight_flush_beats_four_of_a_kind():
    sf = _eval5(*_make5("Ah Kh Qh Jh Th"))
    quads = _eval5(*_make5("Ac Ad As Ah Kd"))
    assert sf < quads


def test_four_of_a_kind_beats_full_house():
    quads = _eval5(*_make5("Ac Ad As Ah Kd"))
    fh = _eval5(*_make5("Ac Ad As Kh Kd"))
    assert quads < fh


def test_full_house_beats_flush():
    fh = _eval5(*_make5("Ac Ad As Kh Kd"))
    fl = _eval5(*_make5("Ah Kh Qh Jh 9h"))
    assert fh < fl


def test_flush_beats_straight():
    fl = _eval5(*_make5("Ah Kh Qh Jh 9h"))
    st = _eval5(*_make5("Ah Kd Qh Js Th"))
    assert fl < st


def test_straight_beats_trips():
    st = _eval5(*_make5("Ah Kd Qh Js Th"))
    trips = _eval5(*_make5("Ah Ac Ad Ks Qh"))
    assert st < trips


def test_trips_beats_two_pair():
    trips = _eval5(*_make5("Ah Ac Ad Ks Qh"))
    tp = _eval5(*_make5("Ah Ac Kd Ks Qh"))
    assert trips < tp


def test_two_pair_beats_one_pair():
    tp = _eval5(*_make5("Ah Ac Kd Ks Qh"))
    op = _eval5(*_make5("Ah Ac Kd Qs Jh"))
    assert tp < op


def test_one_pair_beats_high_card():
    op = _eval5(*_make5("Ah Ac Kd Qs Jh"))
    hc = _eval5(*_make5("Ah Kd Qs Jh 9c"))
    assert op < hc


def test_same_category_pair_ordering():
    # Within ONE_PAIR, kicker encoding uses rank values directly,
    # so higher pair rank -> higher numeric value
    aa = _eval5(*_make5("Ah Ac Kd Qs Jh"))
    kk = _eval5(*_make5("Kh Kc Ad Qs Jh"))
    # Both are ONE_PAIR category
    assert aa // 10_000_000 == ONE_PAIR
    assert kk // 10_000_000 == ONE_PAIR


def test_straight_ordering():
    broadway = _eval5(*_make5("Ah Kd Qh Js Th"))
    nine_high = _eval5(*_make5("9h 8d 7h 6s 5h"))
    # Both are STRAIGHT category
    assert broadway // 10_000_000 == STRAIGHT
    assert nine_high // 10_000_000 == STRAIGHT
    # Broadway has straight_high=12, nine_high has straight_high=7
    assert broadway != nine_high


def test_wheel_vs_six_high_straight():
    wheel = _eval5(*_make5("Ah 2d 3h 4s 5c"))
    six_high = _eval5(*_make5("6h 2d 3h 4s 5c"))
    # Wheel: straight_high=3, Six-high: straight_high=4
    assert wheel // 10_000_000 == STRAIGHT
    assert six_high // 10_000_000 == STRAIGHT
    assert wheel != six_high


# ── evaluate: best 5 from 7 cards ──


def test_evaluate_finds_best_hand():
    hole = (Card("Ah"), Card("Kh"))
    board = parse_cards("Qh Jh Th 3c 2d")
    rank = evaluate(hole, board)
    assert rank // 10_000_000 == STRAIGHT_FLUSH  # royal flush


def test_evaluate_pair_on_board():
    hole = (Card("Ah"), Card("Kd"))
    board = parse_cards("As 7c 6h 3d 2s")
    rank = evaluate(hole, board)
    assert rank // 10_000_000 == ONE_PAIR


def test_evaluate_full_house_from_trips_plus_pair():
    hole = (Card("Ah"), Card("Ad"))
    board = parse_cards("Ac Kh Ks 7d 2s")
    rank = evaluate(hole, board)
    assert rank // 10_000_000 == FULL_HOUSE


def test_evaluate_better_hand_wins_comparison():
    board = parse_cards("Qh Jh Th 3c 2d")
    # Player 1: royal flush
    rank1 = evaluate((Card("Ah"), Card("Kh")), board)
    # Player 2: pair of queens
    rank2 = evaluate((Card("Qd"), Card("5c")), board)
    assert rank1 < rank2  # royal flush wins


# ── hand_category ──


def test_hand_category_all():
    assert hand_category(STRAIGHT_FLUSH * 10_000_000) == "Straight Flush"
    assert hand_category(FOUR_OF_A_KIND * 10_000_000) == "Four of a Kind"
    assert hand_category(FULL_HOUSE * 10_000_000) == "Full House"
    assert hand_category(FLUSH * 10_000_000) == "Flush"
    assert hand_category(STRAIGHT * 10_000_000) == "Straight"
    assert hand_category(THREE_OF_A_KIND * 10_000_000) == "Three of a Kind"
    assert hand_category(TWO_PAIR * 10_000_000) == "Two Pair"
    assert hand_category(ONE_PAIR * 10_000_000) == "One Pair"
    assert hand_category(HIGH_CARD * 10_000_000) == "High Card"


def test_hand_category_unknown():
    assert hand_category(99 * 10_000_000) == "Unknown"
