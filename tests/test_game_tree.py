"""Tests for game_tree.py — Game tree construction."""

import pytest
from poker_solver.game_tree import (
    build_tree, build_river_tree,
    GameNode, Action, NodeType, ActionType, Player, Street,
)


# ── Enums ──


def test_player_values():
    assert Player.OOP.value == 0
    assert Player.IP.value == 1


def test_street_values():
    assert Street.FLOP.value == 0
    assert Street.TURN.value == 1
    assert Street.RIVER.value == 2


def test_action_types():
    for at in ActionType:
        assert at.name in ("CHECK", "BET", "CALL", "FOLD", "RAISE")


# ── Action ──


def test_action_check_repr():
    assert repr(Action(ActionType.CHECK)) == "check"


def test_action_fold_repr():
    assert repr(Action(ActionType.FOLD)) == "fold"


def test_action_call_repr():
    assert repr(Action(ActionType.CALL)) == "call"


def test_action_bet_repr():
    assert repr(Action(ActionType.BET, 50.0)) == "bet:50"


def test_action_raise_repr():
    assert repr(Action(ActionType.RAISE, 100.0)) == "raise:100"


# ── Action keys ──


def test_action_keys():
    node = GameNode(node_type=NodeType.ACTION)
    assert node.action_key(Action(ActionType.CHECK)) == "x"
    assert node.action_key(Action(ActionType.FOLD)) == "f"
    assert node.action_key(Action(ActionType.CALL, 50)) == "c"
    assert node.action_key(Action(ActionType.BET, 67)) == "b67"
    assert node.action_key(Action(ActionType.RAISE, 200)) == "r200"


# ── River tree ──


@pytest.fixture
def river_tree():
    return build_river_tree(
        pot=100, eff_stack=200,
        bet_sizes=[0.5, 1.0],
        raise_sizes=[1.0],
        max_raises=1,
    )


def test_river_root_is_action_node(river_tree):
    assert river_tree.node_type == NodeType.ACTION


def test_river_root_player_is_oop(river_tree):
    assert river_tree.player == Player.OOP


def test_river_root_pot_and_stacks(river_tree):
    assert river_tree.pot == 100
    assert river_tree.stacks == (200, 200)


def test_river_root_street(river_tree):
    assert river_tree.street == Street.RIVER


def test_oop_can_check_or_bet(river_tree):
    action_types = [a.type for a in river_tree.actions]
    assert ActionType.CHECK in action_types
    assert ActionType.BET in action_types


def test_oop_has_two_bet_sizes(river_tree):
    bets = [a for a in river_tree.actions if a.type == ActionType.BET]
    assert len(bets) == 2
    assert bets[0].amount == pytest.approx(50.0)   # 0.5 * 100
    assert bets[1].amount == pytest.approx(100.0)   # 1.0 * 100


def test_check_leads_to_ip_action(river_tree):
    check_child = river_tree.children["x"]
    assert check_child.node_type == NodeType.ACTION
    assert check_child.player == Player.IP


def test_ip_after_check_can_check_or_bet(river_tree):
    ip_node = river_tree.children["x"]
    action_types = [a.type for a in ip_node.actions]
    assert ActionType.CHECK in action_types
    assert ActionType.BET in action_types


def test_check_check_is_showdown(river_tree):
    showdown = river_tree.children["x"].children["x"]
    assert showdown.node_type == NodeType.TERMINAL_SHOWDOWN


def test_bet_leads_to_fold_call_raise(river_tree):
    bet_node = river_tree.children["b50"]
    action_types = [a.type for a in bet_node.actions]
    assert ActionType.FOLD in action_types
    assert ActionType.CALL in action_types
    assert ActionType.RAISE in action_types


def test_fold_is_terminal(river_tree):
    fold_node = river_tree.children["b50"].children["f"]
    assert fold_node.node_type == NodeType.TERMINAL_FOLD
    assert fold_node.folded_player == Player.IP


def test_call_is_showdown(river_tree):
    call_node = river_tree.children["b50"].children["c"]
    assert call_node.node_type == NodeType.TERMINAL_SHOWDOWN


def test_raise_after_max_raises_no_more_raises(river_tree):
    # OOP bets 50, IP raises, OOP faces raise -> fold/call only (max_raises=1)
    raise_node = river_tree.children["b50"]
    # Find IP's raise action
    raise_actions = [a for a in raise_node.actions if a.type == ActionType.RAISE]
    if raise_actions:
        raise_key = raise_node.action_key(raise_actions[0])
        oop_facing = raise_node.children[raise_key]
        oop_action_types = [a.type for a in oop_facing.actions]
        assert ActionType.FOLD in oop_action_types
        assert ActionType.CALL in oop_action_types
        # No more raises after max_raises reached
        assert ActionType.RAISE not in oop_action_types


# ── Turn tree ──


@pytest.fixture
def turn_tree():
    return build_tree(
        street=Street.TURN,
        pot=100, eff_stack=200,
        bet_sizes=[0.5],
        raise_sizes=[1.0],
        max_raises=1,
    )


def test_turn_root_is_turn(turn_tree):
    assert turn_tree.street == Street.TURN


def test_turn_check_check_is_chance_node(turn_tree):
    # OOP checks, IP checks -> chance node (deal river)
    node = turn_tree.children["x"].children["x"]
    assert node.node_type == NodeType.CHANCE


def test_turn_chance_node_has_deal_child(turn_tree):
    chance = turn_tree.children["x"].children["x"]
    assert "deal" in chance.children


def test_turn_deal_leads_to_river_action(turn_tree):
    river_root = turn_tree.children["x"].children["x"].children["deal"]
    assert river_root.node_type == NodeType.ACTION
    assert river_root.player == Player.OOP
    assert river_root.street == Street.RIVER


def test_turn_bet_call_is_chance(turn_tree):
    # OOP bets, IP calls -> chance node
    node = turn_tree.children["b50"].children["c"]
    assert node.node_type == NodeType.CHANCE


def test_turn_fold_is_terminal(turn_tree):
    node = turn_tree.children["b50"].children["f"]
    assert node.node_type == NodeType.TERMINAL_FOLD


# ── Flop tree ──


@pytest.fixture
def flop_tree():
    return build_tree(
        street=Street.FLOP,
        pot=100, eff_stack=200,
        bet_sizes=[0.5],
        raise_sizes=[1.0],
        max_raises=1,
    )


def test_flop_root_is_flop(flop_tree):
    assert flop_tree.street == Street.FLOP


def test_flop_check_check_leads_to_chance(flop_tree):
    node = flop_tree.children["x"].children["x"]
    assert node.node_type == NodeType.CHANCE


def test_flop_chance_leads_to_turn_action(flop_tree):
    turn_root = flop_tree.children["x"].children["x"].children["deal"]
    assert turn_root.street == Street.TURN
    assert turn_root.player == Player.OOP


# ── Backward compatibility ──


def test_build_river_tree_equals_build_tree_river():
    t1 = build_river_tree(100, 200, [0.5], [1.0], 1)
    t2 = build_tree(Street.RIVER, 100, 200, [0.5], [1.0], 1)
    assert t1.pot == t2.pot
    assert t1.stacks == t2.stacks
    assert len(t1.actions) == len(t2.actions)


# ── Node counting / misc ──


def _count_nodes(node: GameNode) -> int:
    count = 1
    for child in node.children.values():
        count += _count_nodes(child)
    return count


def test_minimal_tree_has_expected_nodes():
    # Only 1 bet size, no raises
    tree = build_river_tree(100, 200, [0.5], [], max_raises=0)
    count = _count_nodes(tree)
    assert count > 5


def test_bet_capped_at_stack():
    # Stack is very small, bet should be capped
    tree = build_river_tree(100, 10, [1.0], [1.0], max_raises=1)
    # OOP bet should be min(100, 10) = 10
    bets = [a for a in tree.actions if a.type == ActionType.BET]
    assert all(b.amount <= 10 for b in bets)
