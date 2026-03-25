# River Poker Solver

A heads-up poker solver for the river (final street) that finds an approximate Nash equilibrium via **Counterfactual Regret Minimization (CFR)**.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install numpy

# Optional: GPU acceleration
pip install cupy-cuda12x   # CUDA 12.x
# or
pip install cupy-cuda11x   # CUDA 11.x
```

## Quick Start

```bash
python solver.py
```

Runs with default parameters: board `Ah Kd 7s 3c 2h`, pot 100, stack 200, 1000 CFR iterations.

## CLI Parameters

| Flag | Default | Description |
|---|---|---|
| `--board` | `"Ah Kd 7s 3c 2h"` | 5 board cards separated by spaces |
| `--pot` | `100` | Pot size |
| `--stack` | `200` | Effective stack |
| `--oop` | `"AA,KK,QQ,AK,..."` | OOP player range |
| `--ip` | `"AA,KK,QQ,JJ,..."` | IP player range |
| `--bets` | `"0.67,1.0"` | Bet sizes (pot fractions) |
| `--raises` | `"1.0"` | Raise sizes (pot fractions) |
| `--max-raises` | `1` | Maximum raises per round |
| `--iter` | `1000` | Number of CFR iterations |
| `--gpu` | off | Use GPU via CuPy |

## Range Notation

Standard poker range syntax:

| Syntax | Meaning |
|---|---|
| `AA` | All pocket aces combos (6 combos) |
| `AKs` | Ace-King suited (4 combos) |
| `AKo` | Ace-King offsuit (12 combos) |
| `AK` | All AK combos (suited + offsuit, 16 combos) |
| `JJ+` | Pairs JJ and above (JJ, QQ, KK, AA) |
| `JJ-99` | Pairs from 99 to JJ |
| `ATs+` | Suited hands from ATs and above (ATs, AJs, AQs, AKs) |
| `ATo+` | Offsuit hands from ATo and above |

Combine with commas: `AA,KK,AKs,QJs+,JJ-99`

## Card Notation

- Ranks: `2 3 4 5 6 7 8 9 T J Q K A`
- Suits: `c` (clubs), `d` (diamonds), `h` (hearts), `s` (spades)
- Examples: `Ah` (ace of hearts), `Td` (ten of diamonds), `9c` (nine of clubs)

## Usage Examples

### 1. Standard River Cash Game Spot

Typical NL200 cash game hand. Pot $50, effective stack $150. Dry board, few draws.

```bash
python solver.py \
  --board "As Kc 7d 4h 2s" \
  --pot 50 --stack 150 \
  --oop "AA,KK,AK,AQ,AJ,KQ,KJ,QJ,JT,T9,98,87,76" \
  --ip "AA,KK,QQ,JJ,TT,AK,AQ,AJ,KQ,KJ,QJ,JT,T9" \
  --bets "0.33,0.67,1.0" \
  --iter 20000
```

### 2. Large Pot, Small Stack (SPR < 1)

River after several raises on earlier streets. Less than a pot-size stack remaining — often an all-in situation.

```bash
python solver.py \
  --board "Jh Tc 5d 3s 8c" \
  --pot 300 --stack 150 \
  --oop "AA,KK,QQ,JJ,AJ,KJ,QJ,JT,T8,98,87" \
  --ip "AA,KK,QQ,JJ,TT,AJ,KJ,QJ,JT,T9,98,87" \
  --bets "0.5,1.0" \
  --iter 1000
```

### 3. Wet Board with Completed Draws

Board with flush and straight possibilities. Many nut hands and semi-bluffs.

```bash
python solver.py \
  --board "9h 8h 3d 2c Th" \
  --pot 120 --stack 250 \
  --oop "AA,KhQh,AhKh,Ah5h,Ah4h,Ah3h,Ah2h,KK,QQ,JJ,TT,99,88,JTs,QJs,KQs,T9s,98s,87s,76s" \
  --ip "AA,KhQh,AhKh,Ah5h,Ah4h,KK,QQ,JJ,TT,99,88,JTs,QJs,KQs,AQ,AJ,T9s,98s,87s" \
  --bets "0.33,0.75,1.5" \
  --raises "1.0" \
  --iter 3000
```

### 4. Pot-Size Bet Only (Simplified Tree)

For quick analysis or studying theory. Single bet = pot size, no raises — fast convergence.

```bash
python solver.py \
  --board "Kh Qd 7c 3s 2d" \
  --pot 100 --stack 200 \
  --oop "AA,KK,QQ,AK,AQ,KQ,KJ,QJ,JT,T9,98,87,76,65" \
  --ip "AA,KK,QQ,JJ,TT,AK,AQ,KQ,KJ,QJ,JT,T9,98" \
  --bets "1.0" \
  --max-raises 0 \
  --iter 500
```

### 5. Polarized Range vs Bluff-Catchers

OOP bets or checks on the river. They have only nuts and complete air; IP has medium-strength hands.

```bash
python solver.py \
  --board "As Kd Qc 7h 2s" \
  --pot 200 --stack 400 \
  --oop "AA,KK,AK,AQ,KQ,76s,65s,54s,43s,87s,98s,T9s" \
  --ip "QQ,JJ,TT,99,AJ,AT,KJ,KT,QJ,QT,JT" \
  --bets "0.5,1.0,2.0" \
  --raises "1.0" \
  --iter 2000
```

### 6. Tournament Spot (Short Stack)

Final table, effective stack 15 BB, pot already bloated.

```bash
python solver.py \
  --board "Jc 8d 5s 2h Kc" \
  --pot 24 --stack 12 \
  --oop "AA,KK,QQ,JJ,AK,AQ,AJ,KQ,KJ,QJ,JT,T9,98,87" \
  --ip "AA,KK,QQ,JJ,TT,99,AK,AQ,AJ,AT,KQ,KJ,KT,QJ" \
  --bets "0.5,1.0" \
  --max-raises 0 \
  --iter 1000
```

### 7. River Overbet (2x+ Pot)

Deep stacks. See which hands use the overbet.

```bash
python solver.py \
  --board "Ah 7d 4s 2c Kh" \
  --pot 80 --stack 500 \
  --oop "AA,KK,AK,AQ,AJ,A7s,A4s,A2s,KQ,KJ,QJ,JT,T9,98,87,76,65,54" \
  --ip "AA,KK,QQ,JJ,TT,AK,AQ,AJ,KQ,KJ,KT,QJ,JT,T9,98" \
  --bets "0.33,0.67,1.0,2.0,3.0" \
  --raises "1.0" \
  --iter 3000
```

### 8. GPU Acceleration for Large Ranges

Full ranges with many bet sizes. GPU provides speedup with 300+ combos.

```bash
python solver.py \
  --board "Ts 8c 4d 2h Jd" \
  --pot 100 --stack 300 \
  --oop "AA,KK,QQ,JJ,TT,99,88,77,66,55,44,33,22,AK,AQ,AJ,AT,A9,A8,A5s,A4s,A3s,A2s,KQ,KJ,KT,K9s,QJ,QT,Q9s,JT,J9s,T9s,T8s,98s,97s,87s,86s,76s,75s,65s,54s" \
  --ip "AA,KK,QQ,JJ,TT,99,88,77,66,55,AK,AQ,AJ,AT,A9s,A8s,A5s,A4s,A3s,A2s,KQ,KJ,KT,K9s,K8s,QJ,QT,Q9s,JT,J9s,J8s,T9s,T8s,98s,97s,87s,76s,65s" \
  --bets "0.33,0.67,1.0,1.5" \
  --raises "0.75,1.5" \
  --iter 5000 \
  --gpu
```

## Reading the Output

```
=================================================================
  OOP Strategy (first action)
=================================================================
  Hand       #  Category                  x       b67      b100
  ------   ---  ----------------   --------  --------  --------
  AA         3  Three of a Kind       25.6%      0.4%     74.0%
  AKo        7  Two Pair              49.4%      1.2%     49.4%
  QQ         6  High Card             15.2%      1.5%     83.3%
  QJs        4  High Card             98.0%      0.5%      1.5%
```

- **Hand** — abstract hand (AKs, QQ, etc.)
- **#** — number of concrete combos
- **Category** — poker hand category on the given board
- **x** — check frequency
- **b67** — bet frequency at 67% pot
- **b100** — bet frequency at 100% pot
- Columns sum to ~100% for each hand

## Exploitability Metric

```
Final exploitability: 0.992376
```

Exploitability measures how far the strategy is from Nash equilibrium (in chips per hand). Lower is better. Decreases proportionally to `1/sqrt(iterations)`.

| Exploitability | Solution Quality |
|---|---|
| > 10 | Rough approximation |
| 1 - 10 | Acceptable |
| 0.1 - 1 | Good |
| < 0.1 | Excellent (requires 10000+ iterations) |

## Architecture

```
poker-solver/
  card.py           # Card, parse_cards(), full_deck()
  evaluator.py      # evaluate(hole, board) -> rank
  range_parser.py   # parse_range("AA,AKs,JJ+") -> [(Card, Card), ...]
  game_tree.py      # build_river_tree() -> GameNode tree
  cfr.py            # CFRSolver -- vectorized CFR (NumPy / CuPy)
  solver.py         # CLI entry point
```

### Algorithm

1. **Game tree construction** — all possible action sequences on the river (check, bet, call, fold, raise)
2. **Matrix precomputation** — validity matrix (cards don't overlap) and showdown result matrix
3. **CFR iterations** — at each iteration for every tree node:
   - Compute current strategy via regret matching
   - Recursive traversal with reach probability matrices
   - Update regrets as the difference between a specific action's value and the average value
4. **Average strategy** — averaging strategies across all iterations converges to Nash equilibrium

All operations are vectorized via NumPy/CuPy: instead of looping over every hand pair (O(n^2) Python calls), matrix multiplications are used.
