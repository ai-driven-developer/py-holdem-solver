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

# ── Tree layout constants ──
TNODE_W = 50
TNODE_H = 18
TH_GAP = 6
TV_GAP = 22
TPAD = 10
TREE_H = 130
COLOR_TREE_BG = "#1e1e1e"


def _split_history(history: str) -> list[str]:
    """Split history string into individual action tokens."""
    if not history or history == "root":
        return []
    tokens = []
    i = 0
    while i < len(history):
        if history[i] in ('x', 'f', 'c', '|'):
            tokens.append(history[i])
            i += 1
        elif history[i] in ('b', 'r'):
            j = i + 1
            while j < len(history) and (history[j].isdigit() or history[j] == '.'):
                j += 1
            tokens.append(history[i:j])
            i = j
        else:
            i += 1
    return tokens


def _node_label(token: str) -> str:
    """Short label for a tree node."""
    if token == 'x':
        return 'Chk'
    if token == 'f':
        return 'Fold'
    if token == 'c':
        return 'Call'
    if token == '|':
        return '▸'
    if token.startswith('b'):
        return f'B{token[1:]}'
    if token.startswith('r'):
        return f'R{token[1:]}'
    return token


class _TreeNode:
    """Node in the spot trie used for graphical tree layout."""
    __slots__ = ('children', 'spot_idx', 'label', 'x', 'y', 'width')

    def __init__(self, label: str = ""):
        self.children: dict[str, '_TreeNode'] = {}
        self.spot_idx: int | None = None
        self.label = label
        self.x = 0.0
        self.y = 0.0
        self.width = 0.0


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
        # Tree frame (graphical game tree replaces combobox selector)
        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill="x", pady=(0, 4))

        self._tree_canvas = tk.Canvas(
            tree_frame, height=TREE_H, bg=COLOR_TREE_BG, highlightthickness=0)
        self._tree_xscroll = ttk.Scrollbar(
            tree_frame, orient="horizontal", command=self._tree_canvas.xview)
        self._tree_canvas.configure(xscrollcommand=self._tree_xscroll.set)
        self._tree_canvas.pack(fill="x", side="top")
        self._tree_xscroll.pack(fill="x", side="top")
        self._tree_canvas.bind("<Button-1>", self._on_tree_click)
        self._tree_root: _TreeNode | None = None
        self._tree_spot_items: dict[int, int] = {}  # canvas item id -> spot idx

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
            self._tree_root = None
            self._tree_canvas.delete("all")
            self._clear_grid()
            return

        self._tree_root = self._build_spot_tree()
        self._current_spot = 0
        self._draw_tree()
        self._draw_spot(0)

    # ── Spot tree ──

    def _build_spot_tree(self) -> _TreeNode:
        """Build a trie from spot history strings."""
        root = _TreeNode(label="Root")
        for i, spot in enumerate(self._spots):
            tokens = _split_history(spot["history"])
            if not tokens:
                root.spot_idx = i
                continue
            node = root
            for t in tokens:
                if t not in node.children:
                    node.children[t] = _TreeNode(label=_node_label(t))
                node = node.children[t]
            node.spot_idx = i
        return root

    def _compute_widths(self, node: _TreeNode):
        """Post-order: compute subtree widths for layout."""
        if not node.children:
            node.width = TNODE_W
            return
        for c in node.children.values():
            self._compute_widths(c)
        total = sum(c.width for c in node.children.values())
        total += TH_GAP * max(0, len(node.children) - 1)
        node.width = max(TNODE_W, total)

    def _assign_positions(self, node: _TreeNode, left: float, top: float):
        """Pre-order: assign x, y positions."""
        node.x = left + node.width / 2
        node.y = top
        if not node.children:
            return
        cx = left
        cy = top + TNODE_H + TV_GAP
        for c in node.children.values():
            self._assign_positions(c, cx, cy)
            cx += c.width + TH_GAP

    def _tree_depth(self, node: _TreeNode) -> int:
        if not node.children:
            return 1
        return 1 + max(self._tree_depth(c) for c in node.children.values())

    def _draw_tree(self):
        """Render the spot tree on the tree canvas."""
        canvas = self._tree_canvas
        canvas.delete("all")
        self._tree_spot_items = {}

        if self._tree_root is None:
            return

        self._compute_widths(self._tree_root)
        self._assign_positions(self._tree_root, TPAD, TPAD)
        self._draw_tree_edges(self._tree_root)
        self._draw_tree_nodes(self._tree_root)

        depth = self._tree_depth(self._tree_root)
        tw = self._tree_root.width + TPAD * 2
        th = TPAD * 2 + depth * (TNODE_H + TV_GAP)
        canvas.configure(scrollregion=(0, 0, tw, th))

    def _draw_tree_edges(self, node: _TreeNode):
        canvas = self._tree_canvas
        for c in node.children.values():
            canvas.create_line(
                node.x, node.y + TNODE_H,
                c.x, c.y,
                fill="#454545", width=1)
            self._draw_tree_edges(c)

    def _draw_tree_nodes(self, node: _TreeNode):
        canvas = self._tree_canvas
        x1 = node.x - TNODE_W / 2
        y1 = node.y
        x2 = x1 + TNODE_W
        y2 = y1 + TNODE_H

        is_spot = node.spot_idx is not None
        is_sel = is_spot and node.spot_idx == self._current_spot

        if is_sel:
            fill, outline, txt_c, lw = "#4080c0", "#70b0f0", "#ffffff", 2
        elif is_spot:
            fill, outline, txt_c, lw = "#2e5090", "#4a6a9c", "#dddddd", 1
        elif node.label == "\u25b8":
            fill, outline, txt_c, lw = "#605030", "#807050", "#ccaa66", 1
        else:
            fill, outline, txt_c, lw = "#363636", "#464646", "#999999", 1

        tag = f"spot_{node.spot_idx}" if is_spot else ""
        rid = canvas.create_rectangle(
            x1, y1, x2, y2, fill=fill, outline=outline, width=lw, tags=(tag,))
        tid = canvas.create_text(
            node.x, node.y + TNODE_H / 2,
            text=node.label, fill=txt_c,
            font=("Consolas", 7, "bold"), tags=(tag,))

        if is_spot:
            self._tree_spot_items[rid] = node.spot_idx
            self._tree_spot_items[tid] = node.spot_idx

        for c in node.children.values():
            self._draw_tree_nodes(c)

    def _on_tree_click(self, event):
        cx = self._tree_canvas.canvasx(event.x)
        cy = self._tree_canvas.canvasy(event.y)
        items = self._tree_canvas.find_overlapping(cx - 2, cy - 2, cx + 2, cy + 2)
        for item in items:
            if item in self._tree_spot_items:
                idx = self._tree_spot_items[item]
                self._current_spot = idx
                self._draw_tree()
                self._draw_spot(idx)
                return

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
