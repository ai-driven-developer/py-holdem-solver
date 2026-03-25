#!/usr/bin/env python3
"""Poker solver — main entry point.

Solves heads-up turn or river spots using Counterfactual Regret Minimization (CFR).
Finds approximate Nash equilibrium betting strategies for both players.
"""

import argparse
import json
import time
from collections import defaultdict

from poker_solver.card import Card, parse_cards, RANK_CHARS
from poker_solver.evaluator import hand_category, evaluate
from poker_solver.game_tree import build_tree, Street, Player
from poker_solver.range_parser import parse_range, hand_to_str
from poker_solver.utils import abstract_hand_name, history_label
from poker_solver.cfr import CFRSolver

# Backward-compatible aliases
_abstract_hand_name = abstract_hand_name
_history_label = history_label


def print_strategy_table(solver: CFRSolver, player: Player, board, label: str):
    """Print strategy tables for all decision points, grouped by abstract hand name."""
    rng = solver.oop_range if player == Player.OOP else solver.ip_range
    strategies = solver.get_strategy(player)

    if not strategies:
        print(f"  No strategies computed for {label}")
        return

    # Group entries by history
    by_history: dict[str, dict[str, dict[str, float]]] = defaultdict(dict)
    for key, strat in strategies.items():
        hand_str, history = key.split("@", 1)
        by_history[history][hand_str] = strat

    def _sort_key(h):
        if h == "root":
            return (0, "")
        return (1, h)

    for history in sorted(by_history.keys(), key=_sort_key):
        entries = by_history[history]
        first = next(iter(entries.values()))
        action_names = list(first.keys())

        # Group by abstract hand name, averaging strategies
        group_eval: dict[str, int] = {}
        group_count: dict[str, int] = defaultdict(int)
        group_strat_sum: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))

        for hand in rng:
            hand_str = hand_to_str(hand)
            if hand_str not in entries:
                continue
            abstract = _abstract_hand_name(hand, board)
            strat = entries[hand_str]
            group_count[abstract] += 1
            for a in action_names:
                group_strat_sum[abstract][a] += strat.get(a, 0)
            if abstract not in group_eval:
                group_eval[abstract] = evaluate(hand, board)

        if not group_count:
            continue

        # Average the strategies
        grouped = {}
        for abstract in group_count:
            n = group_count[abstract]
            grouped[abstract] = {a: group_strat_sum[abstract][a] / n for a in action_names}

        sorted_hands = sorted(grouped.keys(), key=lambda h: group_eval[h])

        # Print
        hist_label = _history_label(history)
        actions_header = "  ".join(f"{a:>8}" for a in action_names)
        print(f"\n{'='*65}")
        print(f"  {label} Strategy @ {hist_label}")
        print(f"{'='*65}")
        print(f"  {'Hand':<8} {'#':>3}  {'Category':<18} {actions_header}")
        print(f"  {'-'*6:<8} {'---':>3}  {'-'*16:<18} {'  '.join('-'*8 for _ in action_names)}")

        for abstract in sorted_hands:
            strat = grouped[abstract]
            cat = hand_category(group_eval[abstract])
            n = group_count[abstract]
            probs = "  ".join(f"{strat.get(a, 0):>8.1%}" for a in action_names)
            print(f"  {abstract:<8} {n:>3}  {cat:<18} {probs}")


def _build_strategy_data(solver: CFRSolver, player: Player, board) -> list[dict]:
    """Build structured strategy data for a player across all decision points."""
    rng = solver.oop_range if player == Player.OOP else solver.ip_range
    strategies = solver.get_strategy(player)
    if not strategies:
        return []

    by_history: dict[str, dict[str, dict[str, float]]] = defaultdict(dict)
    for key, strat in strategies.items():
        hand_str, history = key.split("@", 1)
        by_history[history][hand_str] = strat

    def _sort_key(h):
        return (0, "") if h == "root" else (1, h)

    spots = []
    for history in sorted(by_history.keys(), key=_sort_key):
        entries = by_history[history]
        first = next(iter(entries.values()))
        action_names = list(first.keys())

        group_eval: dict[str, int] = {}
        group_count: dict[str, int] = defaultdict(int)
        group_strat_sum: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))

        for hand in rng:
            hand_str = hand_to_str(hand)
            if hand_str not in entries:
                continue
            abstract = _abstract_hand_name(hand, board)
            strat = entries[hand_str]
            group_count[abstract] += 1
            for a in action_names:
                group_strat_sum[abstract][a] += strat.get(a, 0)
            if abstract not in group_eval:
                group_eval[abstract] = evaluate(hand, board)

        if not group_count:
            continue

        hands = []
        for abstract in sorted(group_count.keys(), key=lambda h: group_eval[h]):
            n = group_count[abstract]
            avg = {a: round(group_strat_sum[abstract][a] / n, 4) for a in action_names}
            hands.append({
                "hand": abstract,
                "combos": n,
                "category": hand_category(group_eval[abstract]),
                "strategy": avg,
            })

        spots.append({
            "history": history,
            "label": _history_label(history),
            "actions": action_names,
            "hands": hands,
        })

    return spots


def build_json_output(solver: CFRSolver, board, args) -> dict:
    """Build full JSON-serializable output with metadata and strategies."""
    return {
        "board": args.board,
        "street": {3: "flop", 4: "turn", 5: "river"}[len(board)],
        "pot": args.pot,
        "effective_stack": args.stack,
        "bet_sizes": [float(x) for x in args.bets.split(",")],
        "raise_sizes": [float(x) for x in args.raises.split(",")],
        "iterations": args.iter,
        "exploitability": round(solver.exploitability(), 6),
        "oop": {
            "range": args.oop,
            "combos": solver.n_oop,
            "spots": _build_strategy_data(solver, Player.OOP, board),
        },
        "ip": {
            "range": args.ip,
            "combos": solver.n_ip,
            "spots": _build_strategy_data(solver, Player.IP, board),
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Poker Solver (CFR)")
    parser.add_argument("--board", default="Ah Kd 7s 3c 2h",
                        help="Board cards (3 for flop, 4 for turn, 5 for river)")
    parser.add_argument("--pot", type=float, default=100.0, help="Pot size")
    parser.add_argument("--stack", type=float, default=200.0, help="Effective stack")
    parser.add_argument("--oop", default="AA,KK,QQ,AK,AQ,AJ,KQ,KJ,QJ,JT,T9,98,87,76,65",
                        help="OOP range")
    parser.add_argument("--ip", default="AA,KK,QQ,JJ,TT,AK,AQ,AJ,KQ,KJ,KT,QJ,QT,JT,T9,98",
                        help="IP range")
    parser.add_argument("--bets", default="0.67,1.0",
                        help="Bet sizes as pot fractions (comma-separated)")
    parser.add_argument("--raises", default="1.0",
                        help="Raise sizes as pot fractions (comma-separated)")
    parser.add_argument("--max-raises", type=int, default=1, help="Max raises allowed")
    parser.add_argument("--iter", type=int, default=1000, help="CFR iterations")
    parser.add_argument("--gpu", action="store_true",
                        help="Use GPU via CuPy (pip install cupy-cuda12x)")
    parser.add_argument("--json", metavar="FILE",
                        help="Save strategy to JSON file for UI viewer")
    args = parser.parse_args()

    bet_sizes = [float(x) for x in args.bets.split(",")]
    raise_sizes = [float(x) for x in args.raises.split(",")]

    board = parse_cards(args.board)
    if len(board) == 3:
        street = Street.FLOP
    elif len(board) == 4:
        street = Street.TURN
    elif len(board) == 5:
        street = Street.RIVER
    else:
        parser.error("Board must have 3 (flop), 4 (turn), or 5 (river) cards")

    street_name = {Street.FLOP: "Flop", Street.TURN: "Turn", Street.RIVER: "River"}[street]

    print("=" * 65)
    print(f"  {street_name} Poker Solver (CFR)")
    print("=" * 65)

    oop_range = parse_range(args.oop, board)
    ip_range = parse_range(args.ip, board)

    backend = "GPU (CuPy)" if args.gpu else "CPU (NumPy)"
    print(f"\n  Board:       {args.board}")
    print(f"  Street:      {street_name}")
    print(f"  Pot:         {args.pot:.0f}")
    print(f"  Eff. stack:  {args.stack:.0f}")
    print(f"  Bet sizes:   {[f'{s:.0%}' for s in bet_sizes]} pot")
    print(f"  Raise sizes: {[f'{s:.0%}' for s in raise_sizes]} pot")
    print(f"  OOP range:   {args.oop}  ({len(oop_range)} combos)")
    print(f"  IP range:    {args.ip}  ({len(ip_range)} combos)")
    print(f"  Iterations:  {args.iter}")
    print(f"  Backend:     {backend}")

    # ── Build game tree ──
    print("\n  Building game tree...")
    tree = build_tree(street, args.pot, args.stack, bet_sizes, raise_sizes, args.max_raises)

    # ── Solve ──
    if street == Street.FLOP:
        print(f"  Precomputing turn+river runouts (49 turn × 48 river = 2352 boards)...")
    elif street == Street.TURN:
        print("  Precomputing river runouts (48 cards)...")
    print("  Running CFR...\n")
    solver = CFRSolver(tree, board, oop_range, ip_range, use_gpu=args.gpu)

    t0 = time.time()
    solver.train(args.iter, verbose=True)
    elapsed = time.time() - t0

    print(f"\n  Solved in {elapsed:.1f}s")
    print(f"  Total infoset keys: {len(solver.regrets)}")

    # ── Print strategies ──
    print_strategy_table(solver, Player.OOP, board, "OOP")
    print_strategy_table(solver, Player.IP, board, "IP")

    print(f"\n  Final exploitability: {solver.exploitability():.6f}")

    # ── JSON export ──
    if args.json:
        data = build_json_output(solver, board, args)
        with open(args.json, "w") as f:
            json.dump(data, f, indent=2)
        print(f"  Strategy saved to {args.json}")

    print()


if __name__ == "__main__":
    main()
