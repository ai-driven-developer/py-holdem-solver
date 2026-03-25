# Solver Algorithm Reference

## Table of Contents

1. [Overview](#overview)
2. [Counterfactual Regret Minimization (CFR)](#counterfactual-regret-minimization-cfr)
3. [Game Tree](#game-tree)
4. [Hand Evaluation](#hand-evaluation)
5. [Vectorization and GPU Acceleration](#vectorization-and-gpu-acceleration)
6. [Exploitability Computation](#exploitability-computation)
7. [Multi-Street Solving](#multi-street-solving)

---

## Overview

The solver finds an approximate Nash equilibrium for heads-up poker using
**Counterfactual Regret Minimization (CFR)**. A Nash equilibrium is a strategy
profile in which neither player can improve their expected value by unilaterally
changing their strategy.

Three streets are supported: flop (3 board cards), turn (4 board cards), and
river (5 board cards). On earlier streets the algorithm iterates over all
possible future cards (runouts) to account for uncertainty when computing
the optimal strategy.

---

## Counterfactual Regret Minimization (CFR)

### Core Idea

CFR is an iterative algorithm that converges to a Nash equilibrium in imperfect
information games. On each iteration the algorithm:

1. Traverses the game tree top-down.
2. At every decision node computes the **counterfactual value** of each action —
   the expected payoff given that the player has reached this node.
3. Updates **regrets**: the difference between the value of a specific action
   and the weighted average value across all actions.
4. On the next iteration the strategy is formed via **regret matching** —
   actions with higher accumulated regret receive proportionally more weight.

The average strategy across all iterations converges to a Nash equilibrium at a
rate of **O(1/sqrt(T))**, where T is the number of iterations.

### Regret Matching

The current-iteration strategy is derived from accumulated regrets:

```
strategy[action] = max(regret[action], 0) / sum(max(regret[a], 0) for all a)
```

If all regrets are non-positive the strategy defaults to uniform (1/N for each
of N actions). This guarantees that the algorithm keeps exploring every
available action.

### Tree Traversal (`_cfr`)

The `_cfr` method recursively walks the tree and returns two counterfactual
value vectors — one per player:

- **cf_oop[i]** — counterfactual value for the i-th OOP hand (summed over all
  IP hands weighted by reach probabilities).
- **cf_ip[j]** — likewise for the j-th IP hand.

Formulas at terminal nodes:

```
Showdown:  cf_oop = (valid_result * half_pot) @ reach_ip
Fold:      cf_oop = (valid * sign * half_pot) @ reach_ip
```

Here `@` denotes matrix multiplication, `reach_ip` is the IP reach-probability
vector, and `valid_result` is the showdown outcome matrix.

At action nodes:

```
cf_oop = sum( strategy[:, a] * action_cf_oop[a] )   (acting player is OOP)
cf_ip  = sum( action_cf_ip[a] )                      (simple sum for opponent)
```

### Regret Update

After computing the value of each action, regrets are updated:

```
regret[action] += value[action] - weighted_average_value
```

This accumulates across iterations. Actions that consistently outperform the
average build up positive regret and receive more weight in the strategy.

### Strategy Extraction

The final strategy is the **average strategy** over all iterations, not the
strategy of the last iteration. Each iteration's strategy is weighted by
reach probability and accumulated:

```
strategy_sum[action] += reach_self * strategy[action]
```

The final average strategy:

```
average_strategy[action] = strategy_sum[action] / sum(strategy_sum)
```

---

## Game Tree

### Node Types

The game tree consists of four node types:

| Type | Description |
|------|-------------|
| **ACTION** | Decision node: a player chooses an action (check, bet, raise, call, fold) |
| **CHANCE** | Chance node: the next community card is dealt (turn or river) |
| **TERMINAL_SHOWDOWN** | Showdown: betting is complete, hands are compared |
| **TERMINAL_FOLD** | One player has folded |

### Two Players

- **OOP** (Out Of Position) — acts first.
- **IP** (In Position) — acts second.

Position determines the action order: OOP always acts first on every street.

### Action Structure

The tree is built recursively. On each street:

1. **OOP acts first**: check or bet (one or more sizes).
2. **IP responds**:
   - After OOP checks: check back (ends the street) or bet.
   - After OOP bets: fold, call, or raise.
3. **Raises**: the number of raises is capped by the `max_raises` parameter.
4. **All-in**: if the bet size >= the remaining stack, an all-in is placed.

### Street Transitions

When betting on a street is complete:

- **On the river** -> `TERMINAL_SHOWDOWN`.
- **On the turn** -> `CHANCE` node -> river card is dealt -> new betting round.
- **On the flop** -> `CHANCE` node -> turn card is dealt -> turn betting ->
  `CHANCE` -> river card -> river betting.

### Bet Sizing

Bet sizes are specified as pot fractions:

- `bet_sizes` — fractions for the opening bet (e.g. `[0.33, 0.67, 1.0]`
  means 33%, 67%, and 100% of the pot).
- `raise_sizes` — fractions for a raise (computed from
  `bet_to_call + pot_after_call`).

---

## Hand Evaluation

### Algorithm

The evaluator finds the best 5-card hand from 2 hole cards + N board cards:

1. Enumerates all C(n, 5) combinations of n available cards.
2. For each 5-card combination determines the hand category.
3. Returns the numeric rank of the best combination (lower = stronger).

### Hand Categories (strongest to weakest)

| # | Category | Example |
|---|----------|---------|
| 0 | Straight Flush | A&#9824;K&#9824;Q&#9824;J&#9824;T&#9824; |
| 1 | Four of a Kind | K&#9824;K&#9829;K&#9830;K&#9827;9&#9824; |
| 2 | Full House | Q&#9824;Q&#9829;Q&#9830;J&#9824;J&#9829; |
| 3 | Flush | A&#9824;J&#9824;9&#9824;7&#9824;3&#9824; |
| 4 | Straight | T&#9824;9&#9829;8&#9830;7&#9827;6&#9824; |
| 5 | Three of a Kind | 8&#9824;8&#9829;8&#9830;K&#9824;J&#9829; |
| 6 | Two Pair | A&#9824;A&#9829;7&#9824;7&#9829;K&#9830; |
| 7 | One Pair | J&#9824;J&#9829;A&#9824;K&#9830;9&#9827; |
| 8 | High Card | A&#9824;J&#9829;9&#9830;7&#9827;3&#9824; |

### Rank Encoding

The numeric rank is encoded as:

```
rank = category * 10_000_000 + kickers
```

This allows hands to be compared with a single integer: first by category, then
by kickers.

### Straight Detection

Precomputed bitmasks are used for fast straight detection. Card ranks are
encoded as bits and the mask is looked up against known patterns:

```python
bitmask = 0
for r in ranks:
    bitmask |= 1 << r
straight_high = _STRAIGHT_MASKS.get(bitmask, -1)
```

The wheel (A-2-3-4-5) is handled as a special case.

---

## Vectorization and GPU Acceleration

### Matrix Approach

The solver's main optimization is replacing nested loops over hand pairs with
matrix operations. Instead of iterating over O(n^2) "OOP hand x IP hand" pairs,
the solver uses matrices of shape `[n_oop x n_ip]`.

### Key Matrices

| Matrix | Shape | Contents |
|--------|-------|----------|
| **valid** | [n_oop x n_ip] | 1.0 if the hands share no cards, 0.0 otherwise |
| **result** | [n_oop x n_ip] | sign(eval_ip - eval_oop): +1 if IP wins, -1 if OOP wins, 0 on tie |
| **valid_result** | [n_oop x n_ip] | valid * result — showdown outcome masked by validity |

### Validity Matrix

Two hands form an invalid pair if they share at least one card (collision).
The `valid` matrix is precomputed at initialization:

```python
clash = (oop_card1 == ip_card1) | (oop_card1 == ip_card2) |
        (oop_card2 == ip_card1) | (oop_card2 == ip_card2)
valid = (~clash).astype(float32)
```

When transitioning to a new street the matrix is updated: if the dealt card
matches a card in a player's hand, that hand is excluded.

### Counterfactual Value Computation

Instead of looping over hand pairs, matrix multiplication is used:

```python
# Showdown
cf_oop = (valid_result * half_pot) @ reach_ip      # [n_oop]
cf_ip  = -(valid_result.T @ reach_oop)              # [n_ip]

# Fold
cf_oop = (valid * sign * half_pot) @ reach_ip       # [n_oop]
```

This is the performance-critical operation of the solver.

### GPU Acceleration (CuPy)

When GPU mode is enabled all matrices are transferred to GPU memory and
operations are executed via CuPy (an API-compatible NumPy replacement for CUDA).
This provides a speedup for large hand ranges (200+ combos per player), as
matrix operations parallelize efficiently on the GPU.

Backend selection:

```python
xp = cupy   # if use_gpu=True and CuPy is available
xp = numpy  # otherwise
```

All operations use `xp` instead of `np`, making the code transparently
switchable between CPU and GPU.

---

## Exploitability Computation

### Definition

**Exploitability** measures how far a strategy deviates from Nash equilibrium.
It represents the average number of chips per hand that a perfect opponent
playing a best response can win against the current strategy.

```
exploitability = (BR_oop + BR_ip) / n_valid_pairs
```

Where:
- **BR_oop** — total best-response value for OOP against IP's average strategy.
- **BR_ip** — likewise for IP.
- **n_valid_pairs** — number of valid hand pairs (normalization factor).

### Best Response Algorithm

The `_best_response` method traverses the tree similarly to `_cfr`, but:

- For the **best-response player**: at each decision node the action with the
  maximum value is selected (instead of a weighted mix).
- For the **opponent**: their average strategy is used, and reach probabilities
  are weighted accordingly.

```python
if player == br_player:
    best = max(value[action] for action in actions)    # take the max
else:
    total = sum(avg_strategy[a] * value[a] for a in actions)  # weighted sum
```

### Quality Scale

| Exploitability | Quality |
|----------------|---------|
| > 10 | Rough approximation |
| 1-10 | Acceptable |
| 0.1-1 | Good |
| < 0.1 | Excellent (close to Nash) |

Exploitability decreases as O(1/sqrt(T)), so halving it requires 4x more
iterations.

---

## Multi-Street Solving

### River (5 board cards)

The simplest case: all community cards are known. The showdown result matrix is
precomputed once at initialization.

### Turn (4 board cards)

The river card is unknown on the turn. The algorithm:

1. At initialization precomputes `valid` and `valid_result` matrices for
   **each** of the 48 possible river cards (52 minus 4 board cards).
2. At the `CHANCE` node iterates over all river cards; for each one:
   - Swaps in the corresponding matrices.
   - Recursively solves the river subtree.
3. Averages the results across all river cards.

### Flop (3 board cards)

On the flop both the turn and river cards are unknown. Two-level structure:

1. Matrices are precomputed for all **49 turn cards** (52 - 3).
2. For each turn card, matrices are precomputed for all **48 river cards**
   (52 - 3 board - 1 turn).
3. The first `CHANCE` node iterates over turn cards; the nested one iterates
   over river cards.

### Information Sets (Infosets)

The infoset key depends on the street:

```python
# River
key = (player, history)

# Turn (river subtree)
key = (player, history, river_card_index)

# Flop (turn subtree and river subtree)
key = (player, history, turn_card_index)
key = (player, history, turn_card_index, river_card_index)
```

This ensures correct strategy separation: on the river the strategy depends on
the specific dealt card, not just the betting history.

### Optimization: Mask Caching

For each card (0-51) hand exclusion masks are precomputed:

```python
oop_mask_cache[card_id] = [0.0 if card_id in hand else 1.0 for hand in oop_range]
```

This avoids redundant recomputation when iterating over turn/river cards.

---

## Complexity

| Component | Time Complexity |
|-----------|----------------|
| Single CFR iteration (river) | O(n_nodes x n_oop x n_ip) |
| Single CFR iteration (turn) | O(48 x n_nodes x n_oop x n_ip) |
| Single CFR iteration (flop) | O(49 x 48 x n_nodes x n_oop x n_ip) |
| Showdown precomputation (river) | O(n_oop x n_ip) |
| Showdown precomputation (turn) | O(48 x n_oop x n_ip) |
| Showdown precomputation (flop) | O(49 x 48 x n_oop x n_ip) |
| Single hand evaluation (5 of 7) | O(C(7,5) x 5) = O(105) |

Where `n_nodes` is the number of nodes in the tree on a single street.
