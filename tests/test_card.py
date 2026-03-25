"""Tests for card.py — Card representation and deck utilities."""

import pytest
from poker_solver.card import Card, parse_cards, full_deck, remaining_deck, RANK_CHARS, SUIT_CHARS


# ── Card creation ──


def test_card_create_from_string():
    c = Card("Ah")
    assert c.rank == 12  # A = index 12
    assert c.suit == 2   # SUIT_CHARS = "cdhs", h = index 2
    assert c.rank_char == "A"
    assert c.suit_char == "h"


def test_card_create_from_string_low_card():
    c = Card("2c")
    assert c.rank == 0
    assert c.suit == 0
    assert c.rank_char == "2"
    assert c.suit_char == "c"


def test_card_id_encoding():
    # id = rank * 4 + suit; SUIT_CHARS = "cdhs", h = 2
    c = Card("Ah")
    assert c.id == 12 * 4 + 2  # 50


def test_card_from_id():
    c = Card.from_id(0)
    assert c.rank == 0
    assert c.suit == 0
    assert repr(c) == "2c"


def test_card_from_id_last():
    c = Card.from_id(51)
    assert c.rank == 12
    assert c.suit == 3
    assert repr(c) == "As"  # suit 3 = 's'


def test_card_repr():
    assert repr(Card("Kd")) == "Kd"
    assert repr(Card("Ts")) == "Ts"


def test_card_equality():
    assert Card("Ah") == Card("Ah")
    assert Card("Ah") != Card("Kh")


def test_card_equality_not_implemented():
    assert Card("Ah").__eq__(42) is NotImplemented


def test_card_hash():
    s = {Card("Ah"), Card("Ah"), Card("Kd")}
    assert len(s) == 2


def test_card_lt():
    assert Card("2c") < Card("Ah")
    assert not Card("Ah") < Card("2c")


def test_card_all_ranks_and_suits():
    for i, rc in enumerate(RANK_CHARS):
        for j, sc in enumerate(SUIT_CHARS):
            c = Card(f"{rc}{sc}")
            assert c.rank == i
            assert c.suit == j


# ── parse_cards ──


def test_parse_cards_single():
    cards = parse_cards("Ah")
    assert len(cards) == 1
    assert repr(cards[0]) == "Ah"


def test_parse_cards_multiple():
    cards = parse_cards("Ah Kd 7s 3c 2h")
    assert len(cards) == 5
    assert [repr(c) for c in cards] == ["Ah", "Kd", "7s", "3c", "2h"]


# ── full_deck ──


def test_full_deck_size():
    assert len(full_deck()) == 52


def test_full_deck_unique_ids():
    ids = [c.id for c in full_deck()]
    assert ids == list(range(52))


# ── remaining_deck ──


def test_remaining_deck_excludes_cards():
    excluded = parse_cards("Ah Kd")
    remaining = remaining_deck(excluded)
    assert len(remaining) == 50
    remaining_ids = {c.id for c in remaining}
    assert Card("Ah").id not in remaining_ids
    assert Card("Kd").id not in remaining_ids


def test_remaining_deck_empty_exclusion():
    assert len(remaining_deck([])) == 52
