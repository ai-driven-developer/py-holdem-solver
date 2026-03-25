"""Visual 13x13 strategy grid — shows action frequencies as colored cells."""

import tkinter as tk
from tkinter import ttk

RANKS = list("AKQJT98765432")
CELL_SIZE = 42

# Action color palette (PioSolver-inspired)
ACTION_COLORS = {
    "f":    "#5b8c5b",   # fold — muted green
    "x":    "#4a9e4a",   # check — green
    "c":    "#4a90d9",   # call — blue
    "b33":  "#e8c84a",   # small bet — yellow
    "b50":  "#e8a64a",   # medium bet — orange-yellow
    "b67":  "#e87a4a",   # 2/3 pot — orange
    "b75":  "#e0604a",   # 3/4 pot — red-orange
    "b100": "#d94a4a",   # pot — red
    "b150": "#c42d5b",   # 1.5x pot — magenta-red
    "b200": "#a32d7a",   # 2x pot — purple
}
# Raise colors — slightly brighter variants
RAISE_COLORS = {
    "r50":  "#f0a060",
    "r67":  "#f08050",
    "r75":  "#f06050",
    "r100": "#f04040",
    "r150": "#e030a0",
    "r200": "#c030c0",
}
ACTION_COLORS.update(RAISE_COLORS)

# Fallback palette for unknown actions
_FALLBACK_PALETTE = [
    "#e8c84a", "#e87a4a", "#d94a4a", "#c42d5b", "#a32d7a",
    "#4a90d9", "#4a9e4a", "#5b8c5b", "#7a7ad9", "#d9d94a",
]

COLOR_EMPTY = "#2b2b2b"
COLOR_GRID_BG = "#1a1a1a"


def _cell_label(row: int, col: int) -> str:
    if row == col:
        return f"{RANKS[row]}{RANKS[col]}"
    elif row < col:
        return f"{RANKS[row]}{RANKS[col]}s"
    else:
        return f"{RANKS[col]}{RANKS[row]}o"


def _hand_to_cell(hand: str) -> tuple[int, int] | None:
    """Map abstract hand name to (row, col)."""
    rank_idx = {c: i for i, c in enumerate(RANKS)}
    if len(hand) < 2:
        return None
    r1 = rank_idx.get(hand[0])
    r2 = rank_idx.get(hand[1])
    if r1 is None or r2 is None:
        return None
    suffix = hand[2] if len(hand) > 2 else ""
    if r1 == r2:
        return r1, r2
    elif suffix == "s":
        return min(r1, r2), max(r1, r2)
    else:
        return max(r1, r2), min(r1, r2)


def _action_color(action: str, action_colors: dict[str, str]) -> str:
    return action_colors.get(action, COLOR_EMPTY)


def _assign_colors(actions: list[str]) -> dict[str, str]:
    """Build action->color map, using known colors where possible."""
    result = {}
    fallback_idx = 0
    for a in actions:
        if a in ACTION_COLORS:
            result[a] = ACTION_COLORS[a]
        else:
            # Try prefix match for all-in bets like "b187" etc.
            matched = False
            if a.startswith("b") or a.startswith("r"):
                # Find nearest known size
                prefix = a[0]
                try:
                    size = float(a[1:])
                except ValueError:
                    size = None
                if size is not None:
                    if prefix == "b":
                        if size <= 40:
                            result[a] = "#e8c84a"
                        elif size <= 60:
                            result[a] = "#e8a64a"
                        elif size <= 80:
                            result[a] = "#e87a4a"
                        elif size <= 110:
                            result[a] = "#d94a4a"
                        elif size <= 160:
                            result[a] = "#c42d5b"
                        else:
                            result[a] = "#a32d7a"
                    else:
                        if size <= 80:
                            result[a] = "#f08050"
                        elif size <= 120:
                            result[a] = "#f04040"
                        else:
                            result[a] = "#e030a0"
                    matched = True
            if not matched:
                result[a] = _FALLBACK_PALETTE[fallback_idx % len(_FALLBACK_PALETTE)]
                fallback_idx += 1
    return result


class StrategyViewer(ttk.Frame):
    """13x13 strategy grid with spot selector and legend."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)

        self._spots: list[dict] = []
        self._current_spot = 0
        self._action_colors: dict[str, str] = {}
        # Per-cell strategy: _cell_strat[r][c] = {action: prob} or None
        self._cell_strat: list[list[dict | None]] = [[None] * 13 for _ in range(13)]

        self._build_ui()

    def _build_ui(self):
        # Top bar: spot selector
        top = ttk.Frame(self)
        top.pack(fill="x", pady=(0, 4))

        ttk.Label(top, text="Spot:").pack(side="left")
        self._spot_var = tk.StringVar()
        self._spot_combo = ttk.Combobox(
            top, textvariable=self._spot_var, state="readonly", width=40)
        self._spot_combo.pack(side="left", padx=4)
        self._spot_combo.bind("<<ComboboxSelected>>", self._on_spot_change)

        # Canvas
        grid_size = 13 * CELL_SIZE
        self._canvas = tk.Canvas(
            self, width=grid_size, height=grid_size,
            bg=COLOR_GRID_BG, highlightthickness=0)
        self._canvas.pack(padx=4, pady=4)

        # Pre-create cell items (will be updated later)
        self._cell_rects: list[list[list[int]]] = [[[] for _ in range(13)] for _ in range(13)]
        self._cell_texts: list[list[int]] = [[0] * 13 for _ in range(13)]

        for r in range(13):
            for c in range(13):
                x1, y1 = c * CELL_SIZE, r * CELL_SIZE
                x2, y2 = x1 + CELL_SIZE - 1, y1 + CELL_SIZE - 1
                rect = self._canvas.create_rectangle(
                    x1, y1, x2, y2, fill=COLOR_EMPTY, outline=COLOR_GRID_BG, width=1)
                self._cell_rects[r][c] = [rect]
                label = _cell_label(r, c)
                txt = self._canvas.create_text(
                    (x1 + x2) // 2, (y1 + y2) // 2,
                    text=label, fill="#888888",
                    font=("Consolas", 8, "bold"))
                self._cell_texts[r][c] = txt

        # Tooltip
        self._tooltip = tk.Toplevel(self)
        self._tooltip.wm_overrideredirect(True)
        self._tooltip.withdraw()
        self._tip_label = tk.Label(
            self._tooltip, justify="left", bg="#333333", fg="#ffffff",
            font=("Consolas", 9), padx=6, pady=4, relief="solid", borderwidth=1)
        self._tip_label.pack()

        self._canvas.bind("<Motion>", self._on_motion)
        self._canvas.bind("<Leave>", self._on_leave)

        # Legend frame
        self._legend_frame = ttk.Frame(self)
        self._legend_frame.pack(fill="x", padx=4, pady=(4, 0))

    def set_data(self, spots: list[dict]):
        """Load strategy data (list of spot dicts from solver output)."""
        self._spots = spots
        if not spots:
            self._spot_combo["values"] = []
            self._spot_var.set("")
            self._clear_grid()
            return

        labels = [s["label"] for s in spots]
        self._spot_combo["values"] = labels
        self._spot_var.set(labels[0])
        self._current_spot = 0
        self._draw_spot(0)

    def _on_spot_change(self, _event):
        idx = self._spot_combo.current()
        if idx >= 0:
            self._current_spot = idx
            self._draw_spot(idx)

    def _clear_grid(self):
        self._cell_strat = [[None] * 13 for _ in range(13)]
        for r in range(13):
            for c in range(13):
                # Remove extra rects, keep only one
                for rid in self._cell_rects[r][c][1:]:
                    self._canvas.delete(rid)
                self._cell_rects[r][c] = self._cell_rects[r][c][:1]
                self._canvas.itemconfig(self._cell_rects[r][c][0], fill=COLOR_EMPTY)
                self._canvas.itemconfig(self._cell_texts[r][c], fill="#888888")
                self._canvas.tag_raise(self._cell_texts[r][c])

    def _draw_spot(self, idx: int):
        spot = self._spots[idx]
        actions = spot["actions"]
        hands = spot["hands"]
        self._action_colors = _assign_colors(actions)

        # Clear previous
        self._clear_grid()

        # Map hands to cells
        hand_map: dict[str, dict] = {}
        for h in hands:
            hand_map[h["hand"]] = h["strategy"]

        for r in range(13):
            for c in range(13):
                label = _cell_label(r, c)
                strat = hand_map.get(label)
                if strat is None:
                    self._cell_strat[r][c] = None
                    continue

                self._cell_strat[r][c] = strat
                self._draw_cell(r, c, strat, actions)

        self._update_legend(actions)

    def _draw_cell(self, r: int, c: int, strat: dict, actions: list[str]):
        """Draw colored horizontal bands in a cell proportional to action freqs."""
        x1, y1 = c * CELL_SIZE, r * CELL_SIZE
        x2 = x1 + CELL_SIZE - 1
        cell_h = CELL_SIZE - 1

        # Remove old extra rects
        for rid in self._cell_rects[r][c][1:]:
            self._canvas.delete(rid)
        extra_rects = []

        y_cur = y1
        for a in actions:
            prob = strat.get(a, 0)
            if prob <= 0.005:
                continue
            band_h = max(1, round(prob * cell_h))
            y_end = min(y_cur + band_h, y1 + cell_h)
            color = _action_color(a, self._action_colors)

            if y_cur == y1:
                # Reuse the base rect
                self._canvas.itemconfig(self._cell_rects[r][c][0], fill=color)
                self._canvas.coords(self._cell_rects[r][c][0], x1, y1, x2, y_end)
            else:
                rid = self._canvas.create_rectangle(
                    x1, y_cur, x2, y_end,
                    fill=color, outline="", width=0)
                extra_rects.append(rid)
            y_cur = y_end
            if y_cur >= y1 + cell_h:
                break

        self._cell_rects[r][c] = self._cell_rects[r][c][:1] + extra_rects

        # Text on top
        self._canvas.tag_raise(self._cell_texts[r][c])
        self._canvas.itemconfig(self._cell_texts[r][c], fill="#ffffff")

    def _update_legend(self, actions: list[str]):
        for w in self._legend_frame.winfo_children():
            w.destroy()

        for a in actions:
            color = self._action_colors.get(a, COLOR_EMPTY)
            swatch = tk.Canvas(self._legend_frame, width=14, height=14,
                               bg=color, highlightthickness=1,
                               highlightbackground="#555555")
            swatch.pack(side="left", padx=(4, 1))
            lbl = ttk.Label(self._legend_frame, text=_action_label(a),
                            font=("Consolas", 9))
            lbl.pack(side="left", padx=(0, 8))

    # ── Tooltip ──

    def _on_motion(self, event):
        col = event.x // CELL_SIZE
        row = event.y // CELL_SIZE
        if not (0 <= row < 13 and 0 <= col < 13):
            self._tooltip.withdraw()
            return

        strat = self._cell_strat[row][col]
        if strat is None:
            self._tooltip.withdraw()
            return

        label = _cell_label(row, col)
        lines = [label]
        for a, p in strat.items():
            lines.append(f"  {_action_label(a):<12} {p:>6.1%}")
        self._tip_label.config(text="\n".join(lines))

        x = self.winfo_rootx() + event.x + 16
        y = self.winfo_rooty() + event.y + 16
        self._tooltip.wm_geometry(f"+{x}+{y}")
        self._tooltip.deiconify()

    def _on_leave(self, _event):
        self._tooltip.withdraw()


def _action_label(action: str) -> str:
    """Human-readable action label."""
    if action == "x":
        return "Check"
    if action == "f":
        return "Fold"
    if action == "c":
        return "Call"
    if action.startswith("b"):
        return f"Bet {action[1:]}%"
    if action.startswith("r"):
        return f"Raise {action[1:]}%"
    return action
