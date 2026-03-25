"""Game tree for heads-up poker (OOP vs IP).

Supports flop (3 board cards), turn (4 board cards) and river (5 board cards).
On the flop/turn, betting rounds end with a CHANCE node that transitions
to the next street's betting. On the river, betting ends with a showdown.
"""

from dataclasses import dataclass, field
from enum import Enum, auto


class Player(Enum):
    OOP = 0  # Out of position (acts first)
    IP = 1   # In position (acts second)


class Street(Enum):
    FLOP = 0
    TURN = 1
    RIVER = 2


class ActionType(Enum):
    CHECK = auto()
    BET = auto()
    CALL = auto()
    FOLD = auto()
    RAISE = auto()


@dataclass
class Action:
    type: ActionType
    amount: float = 0.0  # Bet/raise amount (absolute chips)

    def __repr__(self) -> str:
        if self.type in (ActionType.CHECK, ActionType.FOLD, ActionType.CALL):
            return self.type.name.lower()
        return f"{self.type.name.lower()}:{self.amount:.0f}"


class NodeType(Enum):
    ACTION = auto()
    TERMINAL_FOLD = auto()
    TERMINAL_SHOWDOWN = auto()
    CHANCE = auto()


@dataclass
class GameNode:
    node_type: NodeType
    player: Player | None = None
    pot: float = 0.0
    stacks: tuple[float, float] = (0.0, 0.0)
    actions: list[Action] = field(default_factory=list)
    children: dict[str, "GameNode"] = field(default_factory=dict)
    history: str = ""
    # For terminal fold nodes: who folded
    folded_player: Player | None = None
    street: Street = Street.RIVER

    def action_key(self, action: Action) -> str:
        if action.type == ActionType.CHECK:
            return "x"
        elif action.type == ActionType.FOLD:
            return "f"
        elif action.type == ActionType.CALL:
            return "c"
        elif action.type == ActionType.BET:
            return f"b{action.amount:.0f}"
        elif action.type == ActionType.RAISE:
            return f"r{action.amount:.0f}"
        return str(action)


def build_river_tree(
    pot: float,
    eff_stack: float,
    bet_sizes: list[float],
    raise_sizes: list[float],
    max_raises: int = 1,
) -> GameNode:
    """Build a river-only game tree (backward compatibility)."""
    return build_tree(Street.RIVER, pot, eff_stack, bet_sizes, raise_sizes, max_raises)


def build_tree(
    street: Street,
    pot: float,
    eff_stack: float,
    bet_sizes: list[float],
    raise_sizes: list[float],
    max_raises: int = 1,
) -> GameNode:
    """Build a game tree starting from the given street.

    On the turn, completed betting rounds lead to CHANCE nodes
    that transition to river action. On the river, they lead to showdown.
    """
    root = GameNode(
        node_type=NodeType.ACTION,
        player=Player.OOP,
        pot=pot,
        stacks=(eff_stack, eff_stack),
        history="",
        street=street,
    )
    _build_oop_action(root, pot, eff_stack, eff_stack, bet_sizes, raise_sizes,
                      max_raises, "", 0, street)
    return root


def _make_end_of_action(
    pot: float, stacks: tuple[float, float], history: str,
    street: Street, bet_sizes: list[float], raise_sizes: list[float],
    max_raises: int,
) -> GameNode:
    """Create a showdown terminal (river) or chance node (turn).

    On the river, betting ends in a showdown.
    On the turn, betting ends with dealing a river card, then river betting.
    """
    if street == Street.RIVER:
        return GameNode(
            node_type=NodeType.TERMINAL_SHOWDOWN,
            pot=pot, stacks=stacks, history=history, street=street,
        )
    # Chance node → deal river card → river betting
    chance = GameNode(
        node_type=NodeType.CHANCE,
        pot=pot, stacks=stacks, history=history, street=street,
    )
    next_street = Street(street.value + 1)
    next_history = history + "|"
    river_root = GameNode(
        node_type=NodeType.ACTION,
        player=Player.OOP,
        pot=pot, stacks=stacks,
        history=next_history, street=next_street,
    )
    _build_oop_action(river_root, pot, stacks[0], stacks[1],
                      bet_sizes, raise_sizes, max_raises,
                      next_history, 0, next_street)
    chance.children["deal"] = river_root
    return chance


def _build_oop_action(
    node: GameNode, pot: float, stack_oop: float, stack_ip: float,
    bet_sizes: list[float], raise_sizes: list[float],
    max_raises: int, history: str, raise_count: int,
    street: Street,
):
    """Build OOP action node (check or bet)."""
    node.node_type = NodeType.ACTION
    node.player = Player.OOP
    node.pot = pot
    node.stacks = (stack_oop, stack_ip)
    node.history = history
    node.street = street

    # Check
    check_action = Action(ActionType.CHECK)
    check_key = node.action_key(check_action)
    check_node = GameNode(
        node_type=NodeType.ACTION,
        player=Player.IP,
        pot=pot,
        stacks=(stack_oop, stack_ip),
        history=history + check_key,
        street=street,
    )
    node.actions.append(check_action)
    node.children[check_key] = check_node
    _build_ip_after_check(check_node, pot, stack_oop, stack_ip,
                          bet_sizes, raise_sizes, max_raises,
                          history + check_key, street)

    # Bet (various sizes)
    for size_frac in bet_sizes:
        amount = min(pot * size_frac, stack_oop)
        if amount <= 0:
            continue
        bet_action = Action(ActionType.BET, amount)
        bet_key = node.action_key(bet_action)
        bet_node = GameNode(
            node_type=NodeType.ACTION,
            player=Player.IP,
            pot=pot + amount,
            stacks=(stack_oop - amount, stack_ip),
            history=history + bet_key,
            street=street,
        )
        node.actions.append(bet_action)
        node.children[bet_key] = bet_node
        _build_facing_bet(bet_node, pot + amount, stack_oop - amount, stack_ip,
                          amount, Player.IP, bet_sizes, raise_sizes, max_raises,
                          history + bet_key, 0, street)


def _build_ip_after_check(
    node: GameNode, pot: float, stack_oop: float, stack_ip: float,
    bet_sizes: list[float], raise_sizes: list[float],
    max_raises: int, history: str, street: Street,
):
    """Build IP node after OOP checked."""
    node.node_type = NodeType.ACTION
    node.player = Player.IP
    node.pot = pot
    node.stacks = (stack_oop, stack_ip)
    node.history = history
    node.street = street

    # Check back → showdown or next street
    check_action = Action(ActionType.CHECK)
    check_key = node.action_key(check_action)
    node.actions.append(check_action)
    node.children[check_key] = _make_end_of_action(
        pot, (stack_oop, stack_ip), history + check_key,
        street, bet_sizes, raise_sizes, max_raises,
    )

    # Bet
    for size_frac in bet_sizes:
        amount = min(pot * size_frac, stack_ip)
        if amount <= 0:
            continue
        bet_action = Action(ActionType.BET, amount)
        bet_key = node.action_key(bet_action)
        bet_node = GameNode(
            node_type=NodeType.ACTION,
            player=Player.OOP,
            pot=pot + amount,
            stacks=(stack_oop, stack_ip - amount),
            history=history + bet_key,
            street=street,
        )
        node.actions.append(bet_action)
        node.children[bet_key] = bet_node
        _build_facing_bet(bet_node, pot + amount, stack_oop, stack_ip - amount,
                          amount, Player.OOP, bet_sizes, raise_sizes, max_raises,
                          history + bet_key, 0, street)


def _build_facing_bet(
    node: GameNode, pot: float, stack_oop: float, stack_ip: float,
    bet_to_call: float, acting_player: Player,
    bet_sizes: list[float], raise_sizes: list[float], max_raises: int,
    history: str, raise_count: int, street: Street,
):
    """Build node for player facing a bet/raise: fold, call, or raise."""
    node.node_type = NodeType.ACTION
    node.player = acting_player
    node.pot = pot
    node.stacks = (stack_oop, stack_ip)
    node.history = history
    node.street = street

    # Fold
    fold_action = Action(ActionType.FOLD)
    fold_key = node.action_key(fold_action)
    node.actions.append(fold_action)
    node.children[fold_key] = GameNode(
        node_type=NodeType.TERMINAL_FOLD,
        pot=pot,
        stacks=(stack_oop, stack_ip),
        history=history + fold_key,
        folded_player=acting_player,
        street=street,
    )

    # Call
    acting_stack = stack_oop if acting_player == Player.OOP else stack_ip
    call_amount = min(bet_to_call, acting_stack)
    call_action = Action(ActionType.CALL, call_amount)
    call_key = node.action_key(call_action)
    node.actions.append(call_action)

    if acting_player == Player.OOP:
        new_stacks = (stack_oop - call_amount, stack_ip)
    else:
        new_stacks = (stack_oop, stack_ip - call_amount)

    node.children[call_key] = _make_end_of_action(
        pot + call_amount, new_stacks, history + call_key,
        street, bet_sizes, raise_sizes, max_raises,
    )

    # Raise (if allowed)
    if raise_count < max_raises and acting_stack > call_amount:
        for size_frac in raise_sizes:
            raise_total = min(bet_to_call + (pot + call_amount) * size_frac,
                              acting_stack)
            if raise_total <= call_amount:
                continue
            raise_action = Action(ActionType.RAISE, raise_total)
            raise_key = node.action_key(raise_action)

            if acting_player == Player.OOP:
                new_pot = pot + raise_total
                new_stack_oop = stack_oop - raise_total
                new_stack_ip = stack_ip
                next_player = Player.IP
            else:
                new_pot = pot + raise_total
                new_stack_oop = stack_oop
                new_stack_ip = stack_ip - raise_total
                next_player = Player.OOP

            raise_node = GameNode(
                node_type=NodeType.ACTION,
                player=next_player,
                pot=new_pot,
                stacks=(new_stack_oop, new_stack_ip),
                history=history + raise_key,
                street=street,
            )
            node.actions.append(raise_action)
            node.children[raise_key] = raise_node

            new_bet_to_call = raise_total - call_amount
            _build_facing_bet(
                raise_node, new_pot,
                new_stack_oop, new_stack_ip,
                new_bet_to_call, next_player,
                bet_sizes, raise_sizes, max_raises,
                history + raise_key, raise_count + 1, street,
            )
