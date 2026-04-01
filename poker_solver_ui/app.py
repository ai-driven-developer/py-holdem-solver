"""Tkinter GUI for the poker solver."""

import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

from poker_solver.card import parse_cards
from poker_solver.evaluator import evaluate, hand_category
from poker_solver.game_tree import build_tree, Street, Player
from poker_solver.range_parser import parse_range, hand_to_str
from poker_solver.utils import abstract_hand_name, history_label
from poker_solver.cfr import CFRSolver
from poker_solver_ui.range_selector import RangeSelector
from poker_solver_ui.board_selector import BoardSelector
from poker_solver_ui.strategy_viewer import StrategyViewer


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Poker Solver")
        self.geometry("960x780")
        self.resizable(True, True)

        self._solver = None
        self._board = None
        self._running = False

        self._build_ui()

    # ── UI construction ──

    def _build_ui(self):
        params = ttk.LabelFrame(self, text="Parameters", padding=8)
        params.pack(fill="x", padx=8, pady=(8, 4))

        row = 0
        fields = [
            ("Board:", "board", "Ah Kd 7s 3c 2h"),
            ("Pot:", "pot", "100"),
            ("Stack:", "stack", "200"),
            ("OOP range:", "oop", "AA,KK,QQ,AK,AQ,AJ,KQ,KJ,QJ,JT,T9,98,87,76,65"),
            ("IP range:", "ip", "AA,KK,QQ,JJ,TT,AK,AQ,AJ,KQ,KJ,KT,QJ,QT,JT,T9,98"),
            ("Bet sizes:", "bets", "0.67,1.0"),
            ("Raise sizes:", "raises", "1.0"),
            ("Iterations:", "iter", "1000"),
        ]
        self._entries = {}
        for label_text, key, default in fields:
            ttk.Label(params, text=label_text).grid(row=row, column=0, sticky="w", pady=2)
            var = tk.StringVar(value=default)
            entry = ttk.Entry(params, textvariable=var, width=60)
            entry.grid(row=row, column=1, sticky="ew", padx=(4, 0), pady=2)
            self._entries[key] = var
            if key in ("oop", "ip"):
                btn = ttk.Button(params, text="...",  width=3,
                                 command=lambda k=key: self._open_range_selector(k))
                btn.grid(row=row, column=2, padx=(2, 0), pady=2)
            elif key == "board":
                btn = ttk.Button(params, text="...", width=3,
                                 command=self._open_board_selector)
                btn.grid(row=row, column=2, padx=(2, 0), pady=2)
            row += 1

        params.columnconfigure(1, weight=1)

        # Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=8, pady=4)

        self._solve_btn = ttk.Button(btn_frame, text="Solve", command=self._on_solve)
        self._solve_btn.pack(side="left")

        self._progress = ttk.Label(btn_frame, text="")
        self._progress.pack(side="left", padx=8)

        # Results notebook with visual + text tabs
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=(4, 8))

        self._viewer = StrategyViewer(nb)
        self._oop_text = scrolledtext.ScrolledText(nb, font=("Consolas", 10), state="disabled")
        self._ip_text = scrolledtext.ScrolledText(nb, font=("Consolas", 10), state="disabled")
        nb.add(self._viewer, text="Visual")
        nb.add(self._oop_text, text="OOP Table")
        nb.add(self._ip_text, text="IP Table")

    # ── Board selector ──

    def _open_board_selector(self):
        current = self._entries["board"].get().strip()
        dialog = BoardSelector(self, current)
        if dialog.result is not None:
            self._entries["board"].set(dialog.result)

    # ── Range selector ──

    def _open_range_selector(self, key: str):
        label = "OOP Range" if key == "oop" else "IP Range"
        current = self._entries[key].get().strip()
        dialog = RangeSelector(self, label, current)
        if dialog.result is not None:
            self._entries[key].set(dialog.result)

    # ── Solve ──

    def _on_solve(self):
        if self._running:
            return

        # Parse inputs
        try:
            board_str = self._entries["board"].get().strip()
            board = parse_cards(board_str)
            if len(board) not in (3, 4, 5):
                raise ValueError("Board must have 3, 4, or 5 cards")

            pot = float(self._entries["pot"].get())
            stack = float(self._entries["stack"].get())
            oop_str = self._entries["oop"].get().strip()
            ip_str = self._entries["ip"].get().strip()
            bet_sizes = [float(x) for x in self._entries["bets"].get().split(",")]
            raise_sizes = [float(x) for x in self._entries["raises"].get().split(",")]
            iterations = int(self._entries["iter"].get())

            oop_range = parse_range(oop_str, board)
            ip_range = parse_range(ip_str, board)
            if not oop_range or not ip_range:
                raise ValueError("Ranges must not be empty")
        except Exception as e:
            messagebox.showerror("Input Error", str(e))
            return

        street = {3: Street.FLOP, 4: Street.TURN, 5: Street.RIVER}[len(board)]

        self._running = True
        self._solve_btn.config(state="disabled")
        self._progress.config(text="Building tree...")
        self._board = board

        def worker():
            try:
                tree = build_tree(street, pot, stack, bet_sizes, raise_sizes, max_raises=1)
                self.after(0, lambda: self._progress.config(text="Running CFR... 0%"))
                solver = CFRSolver(tree, board, oop_range, ip_range)

                last_expl = [None]

                def on_progress(t, total, expl):
                    pct = t * 100 // total
                    if expl is not None:
                        last_expl[0] = expl
                    if last_expl[0] is not None:
                        txt = f"Running CFR... {pct}%  |  Exploitability: {last_expl[0]:.4f} % pot"
                    else:
                        txt = f"Running CFR... {pct}%"
                    self.after(0, lambda t=txt: self._progress.config(text=t))

                solver.train(iterations, verbose=False, progress_cb=on_progress)
                self._solver = solver
                self.after(0, self._on_done)
            except Exception as e:
                self.after(0, lambda: self._on_error(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _on_error(self, msg):
        self._running = False
        self._solve_btn.config(state="normal")
        self._progress.config(text="")
        messagebox.showerror("Solver Error", msg)

    def _on_done(self):
        self._running = False
        self._solve_btn.config(state="normal")
        expl = self._solver.exploitability()
        self._progress.config(text=f"Done. Exploitability: {expl:.4f} % pot")

        self._show_strategy(self._oop_text, Player.OOP, "OOP")
        self._show_strategy(self._ip_text, Player.IP, "IP")

        # Feed unified visual strategy viewer
        oop_spots = self._build_spot_data(Player.OOP)
        ip_spots = self._build_spot_data(Player.IP)
        self._viewer.set_data(oop_spots, ip_spots)

    # ── Display strategy ──

    def _show_strategy(self, text_widget, player, label):
        solver = self._solver
        board = self._board
        rng = solver.oop_range if player == Player.OOP else solver.ip_range
        strategies = solver.get_strategy(player)

        lines = []
        if not strategies:
            lines.append(f"No strategies for {label}")
        else:
            from collections import defaultdict
            by_history: dict[str, dict] = defaultdict(dict)
            for key, strat in strategies.items():
                hand_str, history = key.split("@", 1)
                by_history[history][hand_str] = strat

            for history in sorted(by_history, key=lambda h: (0, "") if h == "root" else (1, h)):
                entries = by_history[history]
                first = next(iter(entries.values()))
                action_names = list(first.keys())

                group_eval = {}
                group_count = defaultdict(int)
                group_strat_sum = defaultdict(lambda: defaultdict(float))

                for hand in rng:
                    hs = hand_to_str(hand)
                    if hs not in entries:
                        continue
                    abstract = abstract_hand_name(hand, board)
                    strat = entries[hs]
                    group_count[abstract] += 1
                    for a in action_names:
                        group_strat_sum[abstract][a] += strat.get(a, 0)
                    if abstract not in group_eval:
                        group_eval[abstract] = evaluate(hand, board)

                if not group_count:
                    continue

                grouped = {}
                for ab in group_count:
                    n = group_count[ab]
                    grouped[ab] = {a: group_strat_sum[ab][a] / n for a in action_names}

                sorted_hands = sorted(grouped, key=lambda h: group_eval[h])

                hdr = "  ".join(f"{a:>8}" for a in action_names)
                lines.append(f"{'=' * 65}")
                lines.append(f"  {label} @ {history_label(history)}")
                lines.append(f"{'=' * 65}")
                lines.append(f"  {'Hand':<8} {'#':>3}  {'Category':<18} {hdr}")
                lines.append(f"  {'------':<8} {'---':>3}  {'----------------':<18} "
                             + "  ".join("--------" for _ in action_names))

                for ab in sorted_hands:
                    strat = grouped[ab]
                    cat = hand_category(group_eval[ab])
                    n = group_count[ab]
                    probs = "  ".join(f"{strat.get(a, 0):>8.1%}" for a in action_names)
                    lines.append(f"  {ab:<8} {n:>3}  {cat:<18} {probs}")

                lines.append("")

        text_widget.config(state="normal")
        text_widget.delete("1.0", "end")
        text_widget.insert("1.0", "\n".join(lines))
        text_widget.config(state="disabled")

    def _build_spot_data(self, player) -> list[dict]:
        """Build structured spot data for the visual strategy viewer."""
        from collections import defaultdict

        solver = self._solver
        board = self._board
        rng = solver.oop_range if player == Player.OOP else solver.ip_range
        strategies = solver.get_strategy(player)
        if not strategies:
            return []

        by_history: dict[str, dict] = defaultdict(dict)
        for key, strat in strategies.items():
            hand_str, hist = key.split("@", 1)
            by_history[hist][hand_str] = strat

        spots = []
        for hist in sorted(by_history, key=lambda h: (0, "") if h == "root" else (1, h)):
            entries = by_history[hist]
            first = next(iter(entries.values()))
            action_names = list(first.keys())

            group_count: dict[str, int] = defaultdict(int)
            group_strat_sum: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))

            for hand in rng:
                hs = hand_to_str(hand)
                if hs not in entries:
                    continue
                abstract = abstract_hand_name(hand, board)
                strat = entries[hs]
                group_count[abstract] += 1
                for a in action_names:
                    group_strat_sum[abstract][a] += strat.get(a, 0)

            if not group_count:
                continue

            hands = []
            for ab in group_count:
                n = group_count[ab]
                avg = {a: group_strat_sum[ab][a] / n for a in action_names}
                hands.append({"hand": ab, "combos": n, "strategy": avg})

            spots.append({
                "history": hist,
                "label": history_label(hist),
                "actions": action_names,
                "hands": hands,
            })

        return spots


def main():
    app = App()
    app.mainloop()
