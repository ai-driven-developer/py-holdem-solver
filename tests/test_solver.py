"""Tests for solver.py — CLI entry point and strategy printing."""

import pytest
from poker_solver.card import Card, parse_cards
from poker_solver.solver import _abstract_hand_name, print_strategy_table
from poker_solver.game_tree import build_river_tree, Player
from poker_solver.range_parser import parse_range
from poker_solver.cfr import CFRSolver


# ── _abstract_hand_name ──


def test_abstract_hand_name_pocket_pair():
    hand = (Card("Ah"), Card("Ad"))
    board = parse_cards("Kd 7s 3c 2h 5d")
    assert _abstract_hand_name(hand, board) == "AA"


def test_abstract_hand_name_suited():
    hand = (Card("Ah"), Card("Kh"))
    board = parse_cards("Qd 7s 3c 2h 5d")
    assert _abstract_hand_name(hand, board) == "AKs"


def test_abstract_hand_name_offsuit():
    hand = (Card("Ah"), Card("Kd"))
    board = parse_cards("Qd 7s 3c 2h 5d")
    assert _abstract_hand_name(hand, board) == "AKo"


def test_abstract_hand_name_lower_first_card_normalized():
    # If first card rank < second card rank, still returns high first
    hand = (Card("Kd"), Card("Ah"))
    board = parse_cards("Qd 7s 3c 2h 5d")
    assert _abstract_hand_name(hand, board) == "AKo"


def test_abstract_hand_name_low_pair():
    hand = (Card("2c"), Card("2d"))
    board = parse_cards("Ah Kd 7s 3c 5h")
    assert _abstract_hand_name(hand, board) == "22"


def test_abstract_hand_name_suited_connector():
    hand = (Card("9h"), Card("8h"))
    board = parse_cards("Ah Kd 7s 3c 2d")
    assert _abstract_hand_name(hand, board) == "98s"


# ── print_strategy_table ──


def test_print_strategy_table_output(capsys):
    board = parse_cards("Ah Kd 7s 3c 2h")
    tree = build_river_tree(100, 200, [0.5], [], 0)
    oop = parse_range("QQ,JJ", board)
    ip = parse_range("TT,99", board)
    solver = CFRSolver(tree, board, oop, ip)
    solver.train(50, verbose=False)

    print_strategy_table(solver, Player.OOP, board, "OOP")
    captured = capsys.readouterr()
    assert "OOP" in captured.out
    assert "Strategy" in captured.out


def test_print_strategy_table_no_training(capsys):
    board = parse_cards("Ah Kd 7s 3c 2h")
    tree = build_river_tree(100, 200, [0.5], [], 0)
    oop = parse_range("QQ", board)
    ip = parse_range("TT", board)
    solver = CFRSolver(tree, board, oop, ip)
    # Don't train — no strategies computed
    print_strategy_table(solver, Player.OOP, board, "Test")
    captured = capsys.readouterr()
    # Should print something (either strategy or "No strategies")
    assert len(captured.out) > 0


# ── CLI main ──


def test_main_runs(monkeypatch):
    """Test that main() runs with default args."""
    from poker_solver.solver import main
    monkeypatch.setattr(
        "sys.argv",
        ["solver.py", "--iter", "5", "--board", "Ah Kd 7s 3c 2h",
         "--oop", "AA,KK", "--ip", "QQ,JJ"],
    )
    main()  # should not raise


def test_main_turn_mode(monkeypatch):
    from poker_solver.solver import main
    monkeypatch.setattr(
        "sys.argv",
        ["solver.py", "--iter", "3", "--board", "Ah Kd 7s 3c",
         "--oop", "AA", "--ip", "QQ"],
    )
    main()


def test_main_flop_mode(monkeypatch):
    from poker_solver.solver import main
    monkeypatch.setattr(
        "sys.argv",
        ["solver.py", "--iter", "2", "--board", "Ah Kd 7s",
         "--oop", "AA", "--ip", "QQ"],
    )
    main()
