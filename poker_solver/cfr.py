"""Vectorized Counterfactual Regret Minimization (CFR) for poker.

Supports river (5 board cards), turn (4 board cards), and flop (3 board cards).
For turn solving, iterates over all possible river cards at CHANCE nodes.
For flop solving, iterates over all turn cards, then all river cards per turn card.

Supports optional GPU acceleration via CuPy (pip install cupy-cuda12x).
"""

import numpy as np
from poker_solver.card import Card
from poker_solver.evaluator import evaluate
from poker_solver.game_tree import GameNode, NodeType, Player, Street

# ── Array backend: CuPy (GPU) or NumPy (CPU) ──

try:
    import cupy as cp
    _CUPY_AVAILABLE = True
except ImportError:
    _CUPY_AVAILABLE = False


def _get_xp(use_gpu: bool):
    """Return the array module: cupy for GPU, numpy for CPU."""
    if use_gpu:
        if not _CUPY_AVAILABLE:
            print("  [!] CuPy not installed. Falling back to CPU (numpy).")
            print("      Install: pip install cupy-cuda12x")
            return np
        return cp
    return np


class CFRSolver:
    """Vectorized CFR solver for poker (turn or river).

    Args:
        use_gpu: If True and CuPy is installed, run matrix ops on GPU.
                 Most beneficial with large ranges (200+ combos per player).
    """

    def __init__(
        self,
        tree: GameNode,
        board: list[Card],
        oop_range: list[tuple[Card, Card]],
        ip_range: list[tuple[Card, Card]],
        use_gpu: bool = False,
    ):
        self.tree = tree
        self.board = board
        self.oop_range = oop_range
        self.ip_range = ip_range
        self.n_oop = len(oop_range)
        self.n_ip = len(ip_range)
        self.use_gpu = use_gpu and _CUPY_AVAILABLE
        self.xp = _get_xp(use_gpu)
        xp = self.xp

        self.is_flop = len(board) == 3
        self.is_turn = len(board) == 4
        self._current_river_idx = -1
        self._current_turn_idx = -1

        # Precompute base valid matrix: 1.0 if hands don't share cards, else 0.0
        oop_ids = np.array([[h[0].id, h[1].id] for h in oop_range], dtype=np.int32)
        ip_ids = np.array([[h[0].id, h[1].id] for h in ip_range], dtype=np.int32)
        clash = (
            (oop_ids[:, 0, None] == ip_ids[None, :, 0]) |
            (oop_ids[:, 0, None] == ip_ids[None, :, 1]) |
            (oop_ids[:, 1, None] == ip_ids[None, :, 0]) |
            (oop_ids[:, 1, None] == ip_ids[None, :, 1])
        )
        valid_np = (~clash).astype(np.float32)
        oop_cards = [{h[0].id, h[1].id} for h in oop_range]
        ip_cards = [{h[0].id, h[1].id} for h in ip_range]

        self.valid = xp.asarray(valid_np)

        if self.is_flop:
            # Flop mode: precompute turn+river runout data
            self.valid_result = self.valid * 0  # placeholder
            self._precompute_turn_river_data(board, oop_range, ip_range, valid_np,
                                             oop_cards, ip_cards)
            self.oop_eval_values = [evaluate(h, board) for h in oop_range]
        elif self.is_turn:
            # Turn mode: precompute river card showdown data
            self.valid_result = self.valid * 0  # placeholder, swapped at CHANCE nodes
            self._precompute_river_data(board, oop_range, ip_range, valid_np,
                                        oop_cards, ip_cards)
            # For display: evaluate hands on current turn board
            self.oop_eval_values = [evaluate(h, board) for h in oop_range]
        else:
            # River mode: precompute single showdown result
            oop_evals = [evaluate(h, board) for h in oop_range]
            ip_evals = [evaluate(h, board) for h in ip_range]
            self.oop_eval_values = oop_evals

            oop_ev = np.array(oop_evals, dtype=np.int32)
            ip_ev = np.array(ip_evals, dtype=np.int32)
            result_np = np.sign(ip_ev[None, :] - oop_ev[:, None]).astype(np.float32)

            self.result = xp.asarray(result_np)
            self.valid_result = self.valid * self.result

        # Regrets and strategy sums keyed by infoset key
        self.regrets: dict[tuple, any] = {}
        self.strategy_sum: dict[tuple, any] = {}

    def _precompute_river_data(self, board, oop_range, ip_range, valid_np,
                               oop_cards, ip_cards):
        """Precompute showdown matrices for each possible river card."""
        xp = self.xp
        board_ids = {c.id for c in board}
        self.river_cards = [Card.from_id(i) for i in range(52) if i not in board_ids]

        self.river_valid = []
        self.river_valid_result = []

        for rc in self.river_cards:
            rc_id = rc.id
            # River card can't be in either player's hand
            oop_mask = np.array([0.0 if rc_id in ids else 1.0
                                 for ids in oop_cards], dtype=np.float32)
            ip_mask = np.array([0.0 if rc_id in ids else 1.0
                                for ids in ip_cards], dtype=np.float32)
            valid_r = valid_np * np.outer(oop_mask, ip_mask)

            # Showdown results for board + this river card
            full_board = board + [rc]
            oop_evals = [evaluate(h, full_board) for h in oop_range]
            ip_evals = [evaluate(h, full_board) for h in ip_range]

            oop_ev = np.array(oop_evals, dtype=np.int32)
            ip_ev = np.array(ip_evals, dtype=np.int32)
            result_r = np.sign(ip_ev[None, :] - oop_ev[:, None]).astype(np.float32)

            self.river_valid.append(xp.asarray(valid_r))
            self.river_valid_result.append(xp.asarray(valid_r * result_r))

    def _precompute_turn_river_data(self, board, oop_range, ip_range, valid_np,
                                     oop_cards, ip_cards):
        """Precompute showdown matrices for all turn+river runouts (flop mode)."""
        xp = self.xp
        board_ids = {c.id for c in board}
        self.turn_cards = [Card.from_id(i) for i in range(52) if i not in board_ids]

        self.turn_valid = []
        self.turn_river_cards = []
        self.turn_river_valid = []
        self.turn_river_valid_result = []

        oop_mask_cache = {}
        ip_mask_cache = {}
        for cid in range(52):
            oop_mask_cache[cid] = np.array([0.0 if cid in ids else 1.0
                                            for ids in oop_cards], dtype=np.float32)
            ip_mask_cache[cid] = np.array([0.0 if cid in ids else 1.0
                                           for ids in ip_cards], dtype=np.float32)

        for tc in self.turn_cards:
            tc_id = tc.id
            valid_t = valid_np * np.outer(oop_mask_cache[tc_id], ip_mask_cache[tc_id])
            self.turn_valid.append(xp.asarray(valid_t))

            turn_board_ids = board_ids | {tc_id}
            river_cards = [Card.from_id(i) for i in range(52) if i not in turn_board_ids]
            self.turn_river_cards.append(river_cards)

            rv_list = []
            rvr_list = []
            for rc in river_cards:
                rc_id = rc.id
                valid_r = valid_t * np.outer(oop_mask_cache[rc_id], ip_mask_cache[rc_id])

                full_board = board + [tc, rc]
                oop_evals = [evaluate(h, full_board) for h in oop_range]
                ip_evals = [evaluate(h, full_board) for h in ip_range]

                oop_ev = np.array(oop_evals, dtype=np.int32)
                ip_ev = np.array(ip_evals, dtype=np.int32)
                result_r = np.sign(ip_ev[None, :] - oop_ev[:, None]).astype(np.float32)

                rv_list.append(xp.asarray(valid_r))
                rvr_list.append(xp.asarray(valid_r * result_r))

            self.turn_river_valid.append(rv_list)
            self.turn_river_valid_result.append(rvr_list)

    def _infoset_key(self, player: Player, node: GameNode) -> tuple:
        """Build infoset key, including card indices for turn/river nodes."""
        if self.is_flop:
            if node.street == Street.TURN:
                return (player.value, node.history, self._current_turn_idx)
            if node.street == Street.RIVER:
                return (player.value, node.history, self._current_turn_idx,
                        self._current_river_idx)
        elif self.is_turn and node.street == Street.RIVER:
            return (player.value, node.history, self._current_river_idx)
        return (player.value, node.history)

    def _get_strategy(self, key: tuple, n_hands: int, n_actions: int):
        """Compute current strategy via regret matching. Returns [n_hands, n_actions]."""
        xp = self.xp
        if key not in self.regrets:
            self.regrets[key] = xp.zeros((n_hands, n_actions), dtype=xp.float32)
            self.strategy_sum[key] = xp.zeros((n_hands, n_actions), dtype=xp.float32)

        r = xp.maximum(self.regrets[key], 0.0)
        total = r.sum(axis=1, keepdims=True)
        strategy = xp.where(total > 0, r / xp.maximum(total, 1e-30),
                            1.0 / n_actions)
        return strategy

    def _get_average_strategy(self, key: tuple, n_hands: int, n_actions: int):
        """Average strategy (converges to Nash). Returns [n_hands, n_actions]."""
        xp = self.xp
        if key not in self.strategy_sum:
            return xp.full((n_hands, n_actions), 1.0 / n_actions, dtype=xp.float32)
        s = self.strategy_sum[key]
        total = s.sum(axis=1, keepdims=True)
        return xp.where(total > 0, s / xp.maximum(total, 1e-30), 1.0 / n_actions)

    def train(self, iterations: int, verbose: bool = True) -> None:
        """Run vectorized CFR for the given number of iterations."""
        xp = self.xp
        for t in range(1, iterations + 1):
            reach_oop = xp.ones(self.n_oop, dtype=xp.float32)
            reach_ip = xp.ones(self.n_ip, dtype=xp.float32)
            self._cfr(self.tree, reach_oop, reach_ip)

            if verbose and t % max(1, iterations // 10) == 0:
                expl = self.exploitability()
                print(f"  Iteration {t}/{iterations}, exploitability: {expl:.4f}")

    def _cfr(self, node, reach_oop, reach_ip):
        """Vectorized CFR traversal.

        Returns (cf_oop[n_oop], cf_ip[n_ip]):
          cf_oop[i] = sum_j reach_ip[j] * valid[i,j] * utility(i,j)
          cf_ip[j]  = sum_i reach_oop[i] * valid[i,j] * (-utility(i,j))
        """
        xp = self.xp

        # ── Chance node: deal next card ──
        if node.node_type == NodeType.CHANCE:
            child = node.children["deal"]
            cf_oop_total = xp.zeros(self.n_oop, dtype=xp.float32)
            cf_ip_total = xp.zeros(self.n_ip, dtype=xp.float32)

            saved_valid = self.valid
            saved_vr = self.valid_result

            if self.is_flop and node.street == Street.FLOP:
                # Deal turn card — set per-turn river data for nested chance node
                saved_river_cards = getattr(self, 'river_cards', None)
                saved_river_valid = getattr(self, 'river_valid', None)
                saved_river_vr = getattr(self, 'river_valid_result', None)
                saved_turn_idx = self._current_turn_idx

                for t_idx in range(len(self.turn_cards)):
                    self.valid = self.turn_valid[t_idx]
                    self.valid_result = self.valid * 0  # no showdown on turn
                    self._current_turn_idx = t_idx
                    self.river_cards = self.turn_river_cards[t_idx]
                    self.river_valid = self.turn_river_valid[t_idx]
                    self.river_valid_result = self.turn_river_valid_result[t_idx]

                    cf_oop, cf_ip = self._cfr(child, reach_oop, reach_ip)
                    cf_oop_total += cf_oop
                    cf_ip_total += cf_ip

                self.valid = saved_valid
                self.valid_result = saved_vr
                self._current_turn_idx = saved_turn_idx
                self.river_cards = saved_river_cards
                self.river_valid = saved_river_valid
                self.river_valid_result = saved_river_vr

                n = len(self.turn_cards)
            else:
                # Deal river card (turn mode or turn-within-flop)
                for r_idx in range(len(self.river_cards)):
                    self.valid = self.river_valid[r_idx]
                    self.valid_result = self.river_valid_result[r_idx]
                    self._current_river_idx = r_idx

                    cf_oop, cf_ip = self._cfr(child, reach_oop, reach_ip)
                    cf_oop_total += cf_oop
                    cf_ip_total += cf_ip

                self.valid = saved_valid
                self.valid_result = saved_vr
                self._current_river_idx = -1

                n = len(self.river_cards)

            return cf_oop_total / n, cf_ip_total / n

        # ── Terminal: showdown ──
        if node.node_type == NodeType.TERMINAL_SHOWDOWN:
            half_pot = node.pot / 2.0
            payoff = self.valid_result * half_pot
            cf_oop = payoff @ reach_ip
            cf_ip = -(payoff.T @ reach_oop)
            return cf_oop, cf_ip

        # ── Terminal: fold ──
        if node.node_type == NodeType.TERMINAL_FOLD:
            half_pot = node.pot / 2.0
            sign = 1.0 if node.folded_player == Player.IP else -1.0
            m = self.valid * (sign * half_pot)
            cf_oop = m @ reach_ip
            cf_ip = -(m.T @ reach_oop)
            return cf_oop, cf_ip

        # ── Action node ──
        player = node.player
        n_actions = len(node.actions)
        is_oop = (player == Player.OOP)
        n_hands = self.n_oop if is_oop else self.n_ip

        key = self._infoset_key(player, node)
        strategy = self._get_strategy(key, n_hands, n_actions)

        reach_self = reach_oop if is_oop else reach_ip
        self.strategy_sum[key] += reach_self[:, xp.newaxis] * strategy

        action_cf_oop = []
        action_cf_ip = []

        for a_idx, action in enumerate(node.actions):
            child = node.children[node.action_key(action)]
            if is_oop:
                cf_a = self._cfr(child, reach_oop * strategy[:, a_idx], reach_ip)
            else:
                cf_a = self._cfr(child, reach_oop, reach_ip * strategy[:, a_idx])
            action_cf_oop.append(cf_a[0])
            action_cf_ip.append(cf_a[1])

        # ── Combine action values and update regrets ──
        if is_oop:
            cf_oop = sum(strategy[:, a] * action_cf_oop[a] for a in range(n_actions))
            cf_ip = sum(action_cf_ip)
            for a in range(n_actions):
                self.regrets[key][:, a] += action_cf_oop[a] - cf_oop
        else:
            cf_ip = sum(strategy[:, a] * action_cf_ip[a] for a in range(n_actions))
            cf_oop = sum(action_cf_oop)
            for a in range(n_actions):
                self.regrets[key][:, a] += action_cf_ip[a] - cf_ip

        return cf_oop, cf_ip

    # ── Exploitability ──

    def exploitability(self) -> float:
        """Compute exploitability (lower = closer to Nash equilibrium)."""
        xp = self.xp
        opp_reach_for_oop = xp.ones(self.n_ip, dtype=xp.float32)
        opp_reach_for_ip = xp.ones(self.n_oop, dtype=xp.float32)

        br_oop = self._best_response(self.tree, Player.OOP, opp_reach_for_oop)
        br_ip = self._best_response(self.tree, Player.IP, opp_reach_for_ip)

        n_valid = float(self.valid.sum())
        if n_valid == 0:
            return 0.0
        return float(br_oop.sum() + br_ip.sum()) / n_valid

    def _best_response(self, node, br_player, opp_reach):
        """Best-response values for br_player against opponent's average strategy."""
        xp = self.xp
        is_br_oop = (br_player == Player.OOP)

        # ── Chance node ──
        if node.node_type == NodeType.CHANCE:
            child = node.children["deal"]
            n_br = self.n_oop if is_br_oop else self.n_ip
            total = xp.zeros(n_br, dtype=xp.float32)

            saved_valid = self.valid
            saved_vr = self.valid_result

            if self.is_flop and node.street == Street.FLOP:
                saved_river_cards = getattr(self, 'river_cards', None)
                saved_river_valid = getattr(self, 'river_valid', None)
                saved_river_vr = getattr(self, 'river_valid_result', None)
                saved_turn_idx = self._current_turn_idx

                for t_idx in range(len(self.turn_cards)):
                    self.valid = self.turn_valid[t_idx]
                    self.valid_result = self.valid * 0
                    self._current_turn_idx = t_idx
                    self.river_cards = self.turn_river_cards[t_idx]
                    self.river_valid = self.turn_river_valid[t_idx]
                    self.river_valid_result = self.turn_river_valid_result[t_idx]

                    v = self._best_response(child, br_player, opp_reach)
                    total += v

                self.valid = saved_valid
                self.valid_result = saved_vr
                self._current_turn_idx = saved_turn_idx
                self.river_cards = saved_river_cards
                self.river_valid = saved_river_valid
                self.river_valid_result = saved_river_vr

                n = len(self.turn_cards)
            else:
                for r_idx in range(len(self.river_cards)):
                    self.valid = self.river_valid[r_idx]
                    self.valid_result = self.river_valid_result[r_idx]
                    self._current_river_idx = r_idx

                    v = self._best_response(child, br_player, opp_reach)
                    total += v

                self.valid = saved_valid
                self.valid_result = saved_vr
                self._current_river_idx = -1

                n = len(self.river_cards)

            return total / n

        if node.node_type == NodeType.TERMINAL_SHOWDOWN:
            half_pot = node.pot / 2.0
            if is_br_oop:
                return (self.valid_result * half_pot) @ opp_reach
            else:
                return -(self.valid_result * half_pot).T @ opp_reach

        if node.node_type == NodeType.TERMINAL_FOLD:
            half_pot = node.pot / 2.0
            if is_br_oop:
                sign = 1.0 if node.folded_player == Player.IP else -1.0
                return (self.valid * sign * half_pot) @ opp_reach
            else:
                sign = 1.0 if node.folded_player == Player.OOP else -1.0
                return (self.valid * sign * half_pot).T @ opp_reach

        player = node.player
        n_actions = len(node.actions)
        is_oop = (player == Player.OOP)
        n_hands = self.n_oop if is_oop else self.n_ip

        key = self._infoset_key(player, node)
        avg_strategy = self._get_average_strategy(key, n_hands, n_actions)

        if player == br_player:
            best = None
            for a_idx, action in enumerate(node.actions):
                child = node.children[node.action_key(action)]
                v = self._best_response(child, br_player, opp_reach)
                best = v.copy() if best is None else xp.maximum(best, v)
            return best
        else:
            total = None
            for a_idx, action in enumerate(node.actions):
                child = node.children[node.action_key(action)]
                new_opp = opp_reach * avg_strategy[:, a_idx]
                v = self._best_response(child, br_player, new_opp)
                total = v if total is None else total + v
            return total

    # ── Strategy extraction ──

    def get_strategy(self, player: Player) -> dict[str, dict[str, float]]:
        """Get average strategy for a player.

        Returns {f"{hand}@{history}": {action: probability}}.
        For turn mode, only returns turn-level strategies (not per-river-card).
        """
        xp = self.xp
        rng = self.oop_range if player == Player.OOP else self.ip_range
        is_oop = (player == Player.OOP)
        n_hands = self.n_oop if is_oop else self.n_ip
        result = {}

        def _collect(nd: GameNode):
            # Don't descend into river subtrees in turn mode
            if nd.node_type == NodeType.CHANCE:
                return

            if nd.node_type != NodeType.ACTION or nd.player != player:
                for ch in nd.children.values():
                    _collect(ch)
                return

            n_act = len(nd.actions)
            key = (player.value, nd.history)
            avg = self._get_average_strategy(key, n_hands, n_act)
            # Transfer to CPU for dict construction
            if self.use_gpu:
                avg_cpu = avg.get()
            else:
                avg_cpu = avg

            for h_idx, hand in enumerate(rng):
                hand_str = f"{hand[0]}{hand[1]}"
                hist = nd.history if nd.history else "root"
                entry = f"{hand_str}@{hist}"
                result[entry] = {
                    nd.action_key(a): float(avg_cpu[h_idx, a_idx])
                    for a_idx, a in enumerate(nd.actions)
                }

            for ch in nd.children.values():
                _collect(ch)

        _collect(self.tree)
        return result
