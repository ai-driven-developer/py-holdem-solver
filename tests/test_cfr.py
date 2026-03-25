"""Tests for cfr.py — CFR solver algorithm."""

import pytest
import numpy as np
from poker_solver.card import Card, parse_cards
from poker_solver.game_tree import build_tree, build_river_tree, Street, Player, NodeType
from poker_solver.range_parser import parse_range
from poker_solver.cfr import CFRSolver


def _make_river_solver(
    board_str="Ah Kd 7s 3c 2h",
    oop_range_str="AA,KK",
    ip_range_str="QQ,JJ",
    pot=100, stack=200,
    bet_sizes=None, raise_sizes=None,
    max_raises=1, iterations=0,
):
    """Helper to create a river CFR solver."""
    if bet_sizes is None:
        bet_sizes = [0.5]
    if raise_sizes is None:
        raise_sizes = [1.0]
    board = parse_cards(board_str)
    tree = build_river_tree(pot, stack, bet_sizes, raise_sizes, max_raises)
    oop_range = parse_range(oop_range_str, board)
    ip_range = parse_range(ip_range_str, board)
    solver = CFRSolver(tree, board, oop_range, ip_range)
    if iterations > 0:
        solver.train(iterations, verbose=False)
    return solver


# ── Init ──


def test_cfr_creates_solver():
    solver = _make_river_solver()
    assert solver.n_oop > 0
    assert solver.n_ip > 0


def test_cfr_valid_matrix_shape():
    solver = _make_river_solver()
    assert solver.valid.shape == (solver.n_oop, solver.n_ip)


def test_cfr_valid_matrix_no_card_overlap():
    solver = _make_river_solver()
    # All entries should be 0 or 1
    valid_np = np.array(solver.valid)
    assert np.all((valid_np == 0) | (valid_np == 1))


def test_cfr_result_matrix_values():
    solver = _make_river_solver()
    result_np = np.array(solver.result)
    # Result should be -1, 0, or 1
    assert np.all(np.isin(result_np, [-1.0, 0.0, 1.0]))


def test_cfr_valid_result_masks_overlap():
    solver = _make_river_solver()
    valid_np = np.array(solver.valid)
    vr_np = np.array(solver.valid_result)
    # Where valid is 0, valid_result must be 0
    assert np.all(vr_np[valid_np == 0] == 0)


def test_cfr_range_sizes():
    solver = _make_river_solver(oop_range_str="AA", ip_range_str="KK")
    board = parse_cards("Ah Kd 7s 3c 2h")
    # AA with Ah on board: 3 combos, KK with Kd on board: 3 combos
    assert solver.n_oop == 3
    assert solver.n_ip == 3


# ── Training ──


def test_cfr_train_runs():
    solver = _make_river_solver(iterations=10)
    assert len(solver.regrets) > 0
    assert len(solver.strategy_sum) > 0


def test_cfr_exploitability_decreases():
    solver = _make_river_solver()
    solver.train(50, verbose=False)
    expl1 = solver.exploitability()
    solver.train(200, verbose=False)
    expl2 = solver.exploitability()
    # More iterations should reduce exploitability
    assert expl2 <= expl1 + 0.1  # allow small tolerance


def test_cfr_exploitability_is_nonnegative():
    solver = _make_river_solver(iterations=100)
    assert solver.exploitability() >= -1e-6


def test_cfr_converges_to_low_exploitability():
    solver = _make_river_solver(
        oop_range_str="AA,KK,QQ",
        ip_range_str="JJ,TT,99",
        iterations=500,
    )
    expl = solver.exploitability()
    assert expl < 5.0  # should converge reasonably


# ── Strategy extraction ──


def test_cfr_get_strategy_returns_dict():
    solver = _make_river_solver(iterations=50)
    strat = solver.get_strategy(Player.OOP)
    assert isinstance(strat, dict)
    assert len(strat) > 0


def test_cfr_strategy_probabilities_sum_to_one():
    solver = _make_river_solver(iterations=100)
    for player in [Player.OOP, Player.IP]:
        strat = solver.get_strategy(player)
        for key, action_probs in strat.items():
            total = sum(action_probs.values())
            assert abs(total - 1.0) < 0.01, f"Probs sum to {total} for {key}"


def test_cfr_strategy_has_expected_actions():
    solver = _make_river_solver(iterations=50)
    strat = solver.get_strategy(Player.OOP)
    # Root OOP should have check and bet actions
    root_entries = {k: v for k, v in strat.items() if k.endswith("@root")}
    assert len(root_entries) > 0
    first = next(iter(root_entries.values()))
    assert "x" in first  # check
    assert any(k.startswith("b") for k in first)  # bet


# ── Strategic behavior ──


def test_cfr_strong_hand_bets_more():
    """With nuts vs air, the solver should bet aggressively."""
    solver = _make_river_solver(
        board_str="Ah Kd 7s 3c 2h",
        oop_range_str="AA",
        ip_range_str="55,44",
        iterations=300,
    )
    strat = solver.get_strategy(Player.OOP)
    root_entries = {k: v for k, v in strat.items() if k.endswith("@root")}
    # AA should bet frequently since it always wins
    for key, probs in root_entries.items():
        bet_prob = sum(v for k, v in probs.items() if k.startswith("b"))
        assert bet_prob > 0.3


# ── Turn mode ──


def test_cfr_turn_solver_creates():
    board = parse_cards("Ah Kd 7s 3c")
    tree = build_tree(Street.TURN, 100, 200, [0.5], [1.0], 1)
    oop = parse_range("AA", board)
    ip = parse_range("QQ", board)
    solver = CFRSolver(tree, board, oop, ip)
    assert solver.is_turn
    assert not solver.is_flop


def test_cfr_turn_solver_trains():
    board = parse_cards("Ah Kd 7s 3c")
    tree = build_tree(Street.TURN, 100, 200, [0.5], [], 0)
    oop = parse_range("AA", board)
    ip = parse_range("QQ", board)
    solver = CFRSolver(tree, board, oop, ip)
    solver.train(20, verbose=False)
    expl = solver.exploitability()
    assert expl >= 0


# ── Edge cases ──


def test_cfr_single_combo_each():
    # Minimal ranges: 1 combo each
    board = parse_cards("Ah Kd 7s 3c 2h")
    tree = build_river_tree(100, 200, [0.5], [], 0)
    oop = [(Card("Qs"), Card("Qc"))]
    ip = [(Card("Js"), Card("Jc"))]
    solver = CFRSolver(tree, board, oop, ip)
    solver.train(50, verbose=False)
    assert solver.exploitability() >= 0


def test_cfr_no_raises_tree():
    solver = _make_river_solver(
        raise_sizes=[], max_raises=0, iterations=50,
    )
    strat = solver.get_strategy(Player.OOP)
    assert len(strat) > 0


def test_cfr_verbose_training(capsys):
    solver = _make_river_solver()
    solver.train(10, verbose=True)
    captured = capsys.readouterr()
    assert "Iteration" in captured.out
