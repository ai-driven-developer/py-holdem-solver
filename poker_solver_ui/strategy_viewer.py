"""Unified visual strategy viewer — left-to-right expandable tree + 13×13 strategy grid."""

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

# ── Tree layout constants (left-to-right) ──
TNODE_W = 76
TNODE_H = 22
TH_GAP = 20       # horizontal gap between depth levels
TV_GAP = 4         # vertical gap between siblings
TPAD = 8
COLOR_TREE_BG = "#1e1e1e"

# Player node colors
COLOR_OOP_NODE = "#7a3b3b"
COLOR_OOP_SEL = "#b05555"
COLOR_IP_NODE = "#3b4a7a"
COLOR_IP_SEL = "#5570b0"


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
        return '\u25b8'
    if token.startswith('b'):
        return f'B{token[1:]}'
    if token.startswith('r'):
        return f'R{token[1:]}'
    return token


class _TreeNode:
    """Node in the unified game-tree trie for graphical layout."""
    __slots__ = ('children', 'spot_idx', 'player', 'label', 'token',
                 'x', 'y', 'height', 'expanded', 'action_pct')

    def __init__(self, label: str = "", token: str = ""):
        self.children: dict[str, '_TreeNode'] = {}
        self.spot_idx: int | None = None
        self.player: str = ""          # "OOP" or "IP"
        self.label = label
        self.token = token
        self.x = 0.0
        self.y = 0.0
        self.height = 0.0
        self.expanded = False
        self.action_pct: float | None = None  # aggregate freq from parent


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
            matched = False
            if a.startswith("b") or a.startswith("r"):
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


class StrategyViewer(ttk.Frame):
    """Unified strategy viewer: left-to-right expandable game tree + 13x13 grid."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)

        self._oop_spots: list[dict] = []
        self._ip_spots: list[dict] = []
        self._current_node: _TreeNode | None = None
        self._action_colors: dict[str, str] = {}
        self._cell_strat: list[list[dict | None]] = [[None] * 13 for _ in range(13)]
        self._tree_root: _TreeNode | None = None
        self._tree_node_items: dict[int, _TreeNode] = {}

        self._build_ui()

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)
        self.rowconfigure(0, weight=1)

        # ── Left: tree panel ──
        tree_frame = ttk.Frame(self)
        tree_frame.grid(row=0, column=0, sticky="nsew")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        self._tree_canvas = tk.Canvas(
            tree_frame, bg=COLOR_TREE_BG, highlightthickness=0, width=250)
        self._tree_yscroll = ttk.Scrollbar(
            tree_frame, orient="vertical", command=self._tree_canvas.yview)
        self._tree_xscroll = ttk.Scrollbar(
            tree_frame, orient="horizontal", command=self._tree_canvas.xview)
        self._tree_canvas.configure(
            yscrollcommand=self._tree_yscroll.set,
            xscrollcommand=self._tree_xscroll.set)

        self._tree_canvas.grid(row=0, column=0, sticky="nsew")
        self._tree_yscroll.grid(row=0, column=1, sticky="ns")
        self._tree_xscroll.grid(row=1, column=0, sticky="ew")

        self._tree_canvas.bind("<Button-1>", self._on_tree_click)
        # Mouse wheel scrolling
        self._tree_canvas.bind("<Button-4>",
                               lambda e: self._tree_canvas.yview_scroll(-3, "units"))
        self._tree_canvas.bind("<Button-5>",
                               lambda e: self._tree_canvas.yview_scroll(3, "units"))
        self._tree_canvas.bind("<Shift-Button-4>",
                               lambda e: self._tree_canvas.xview_scroll(-3, "units"))
        self._tree_canvas.bind("<Shift-Button-5>",
                               lambda e: self._tree_canvas.xview_scroll(3, "units"))

        # ── Right: grid + legend ──
        right_frame = ttk.Frame(self)
        right_frame.grid(row=0, column=1, sticky="ns", padx=(4, 0))

        # Player / spot label
        self._player_label = ttk.Label(
            right_frame, text="", font=("Consolas", 10, "bold"))
        self._player_label.pack(pady=(4, 2))

        # Grid canvas
        grid_size = 13 * CELL_SIZE
        self._canvas = tk.Canvas(
            right_frame, width=grid_size, height=grid_size,
            bg=COLOR_GRID_BG, highlightthickness=0)
        self._canvas.pack(padx=4, pady=4)

        # Pre-create cell items
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
        self._legend_frame = ttk.Frame(right_frame)
        self._legend_frame.pack(fill="x", padx=4, pady=(4, 0))

    # ── Public API ──

    def set_data(self, oop_spots: list[dict], ip_spots: list[dict]):
        """Load strategy data for both players and build unified tree."""
        self._oop_spots = oop_spots
        self._ip_spots = ip_spots

        if not oop_spots and not ip_spots:
            self._tree_root = None
            self._current_node = None
            self._tree_canvas.delete("all")
            self._clear_grid()
            self._player_label.config(text="")
            return

        self._tree_root = self._build_unified_tree()
        self._compute_action_pcts(self._tree_root)

        # Expand root by default
        self._tree_root.expanded = True
        self._current_node = self._tree_root

        self._draw_tree()

        # Show root spot grid if it's a decision point
        if self._tree_root.spot_idx is not None:
            self._show_node_grid(self._tree_root)
        else:
            self._clear_grid()
            self._player_label.config(text="")

    # ── Unified tree construction ──

    def _build_unified_tree(self) -> _TreeNode:
        """Build a trie from both OOP and IP spot history strings."""
        root = _TreeNode(label="Root", token="")

        for i, spot in enumerate(self._oop_spots):
            tokens = _split_history(spot["history"])
            node = root
            if not tokens:
                node.spot_idx = i
                node.player = "OOP"
                continue
            for t in tokens:
                if t not in node.children:
                    node.children[t] = _TreeNode(label=_node_label(t), token=t)
                node = node.children[t]
            node.spot_idx = i
            node.player = "OOP"

        for i, spot in enumerate(self._ip_spots):
            tokens = _split_history(spot["history"])
            node = root
            if not tokens:
                node.spot_idx = i
                node.player = "IP"
                continue
            for t in tokens:
                if t not in node.children:
                    node.children[t] = _TreeNode(label=_node_label(t), token=t)
                node = node.children[t]
            node.spot_idx = i
            node.player = "IP"

        return root

    def _compute_action_pcts(self, node: _TreeNode):
        """Compute aggregate action percentages and assign to children nodes."""
        if node.spot_idx is not None and node.children:
            spots = self._oop_spots if node.player == "OOP" else self._ip_spots
            spot = spots[node.spot_idx]
            total_combos = sum(h["combos"] for h in spot["hands"])
            if total_combos > 0:
                for action_key, child in node.children.items():
                    freq = sum(
                        h["strategy"].get(action_key, 0) * h["combos"]
                        for h in spot["hands"]
                    ) / total_combos
                    child.action_pct = freq

        for c in node.children.values():
            self._compute_action_pcts(c)

    # ── Tree layout (left-to-right) ──

    def _compute_heights(self, node: _TreeNode):
        """Post-order: compute subtree heights for vertical spread."""
        if not node.children or not node.expanded:
            node.height = TNODE_H
            return
        for c in node.children.values():
            self._compute_heights(c)
        total = sum(c.height for c in node.children.values())
        total += TV_GAP * max(0, len(node.children) - 1)
        node.height = max(TNODE_H, total)

    def _assign_positions(self, node: _TreeNode, left: float, top: float):
        """Pre-order: assign x (left edge), y (vertical center)."""
        node.x = left
        node.y = top + node.height / 2
        if not node.children or not node.expanded:
            return
        cx = left + TNODE_W + TH_GAP
        cy = top
        for c in node.children.values():
            self._assign_positions(c, cx, cy)
            cy += c.height + TV_GAP

    def _tree_bounds(self, node: _TreeNode) -> tuple[float, float]:
        """Compute max x, max y of the visible tree."""
        max_x = node.x + TNODE_W
        max_y = node.y + TNODE_H / 2
        if node.expanded:
            for c in node.children.values():
                cx, cy = self._tree_bounds(c)
                max_x = max(max_x, cx)
                max_y = max(max_y, cy)
        return max_x, max_y

    def _draw_tree(self):
        """Render the full visible tree on the tree canvas."""
        canvas = self._tree_canvas
        canvas.delete("all")
        self._tree_node_items = {}

        if self._tree_root is None:
            return

        self._compute_heights(self._tree_root)
        self._assign_positions(self._tree_root, TPAD, TPAD)
        self._draw_tree_edges(self._tree_root)
        self._draw_tree_nodes(self._tree_root)

        max_x, max_y = self._tree_bounds(self._tree_root)
        canvas.configure(scrollregion=(0, 0, max_x + TPAD, max_y + TPAD))

    def _draw_tree_edges(self, node: _TreeNode):
        if not node.expanded:
            return
        canvas = self._tree_canvas
        for c in node.children.values():
            canvas.create_line(
                node.x + TNODE_W, node.y,
                c.x, c.y,
                fill="#454545", width=1)
            self._draw_tree_edges(c)

    def _draw_tree_nodes(self, node: _TreeNode):
        canvas = self._tree_canvas
        x1 = node.x
        y1 = node.y - TNODE_H / 2
        x2 = x1 + TNODE_W
        y2 = y1 + TNODE_H

        is_sel = (node is self._current_node)
        has_children = bool(node.children)

        # Colors based on player
        if node.player == "OOP":
            fill = COLOR_OOP_SEL if is_sel else COLOR_OOP_NODE
            outline = "#e07070" if is_sel else "#b06060"
        elif node.player == "IP":
            fill = COLOR_IP_SEL if is_sel else COLOR_IP_NODE
            outline = "#7090e0" if is_sel else "#6080b0"
        elif node.label == "\u25b8":
            fill, outline = "#605030", "#807050"
        else:
            fill = "#505050" if is_sel else "#363636"
            outline = "#707070" if is_sel else "#464646"

        txt_c = "#ffffff" if is_sel else "#dddddd"
        lw = 2 if is_sel else 1

        # Build display text
        display = node.label
        if node.action_pct is not None:
            pct = node.action_pct * 100
            display += f" {pct:.0f}%"

        # Expand/collapse indicator for nodes with children
        if has_children:
            indicator = "\u25bc" if node.expanded else "\u25b6"
            display = indicator + " " + display

        rid = canvas.create_rectangle(
            x1, y1, x2, y2, fill=fill, outline=outline, width=lw)
        tid = canvas.create_text(
            (x1 + x2) / 2, (y1 + y2) / 2,
            text=display, fill=txt_c, font=("Consolas", 7, "bold"))

        self._tree_node_items[rid] = node
        self._tree_node_items[tid] = node

        # Draw children if expanded
        if node.expanded:
            for c in node.children.values():
                self._draw_tree_nodes(c)

    # ── Tree interaction ──

    def _on_tree_click(self, event):
        cx = self._tree_canvas.canvasx(event.x)
        cy = self._tree_canvas.canvasy(event.y)
        items = self._tree_canvas.find_overlapping(cx - 2, cy - 2, cx + 2, cy + 2)

        clicked_node = None
        for item in items:
            if item in self._tree_node_items:
                clicked_node = self._tree_node_items[item]
                break

        if clicked_node is None:
            return

        if clicked_node is self._current_node:
            # Already selected — toggle expand/collapse
            if clicked_node.children:
                clicked_node.expanded = not clicked_node.expanded
        else:
            # New selection — select and expand
            self._current_node = clicked_node
            if clicked_node.children and not clicked_node.expanded:
                clicked_node.expanded = True
            if clicked_node.spot_idx is not None:
                self._show_node_grid(clicked_node)

        self._draw_tree()

    # ── Grid display ──

    def _show_node_grid(self, node: _TreeNode):
        """Show the 13x13 strategy grid for the given tree node."""
        spots = self._oop_spots if node.player == "OOP" else self._ip_spots
        spot = spots[node.spot_idx]
        actions = spot["actions"]
        hands = spot["hands"]
        self._action_colors = _assign_colors(actions)

        self._clear_grid()

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
        self._player_label.config(text=f"{node.player} @ {spot['label']}")

    def _clear_grid(self):
        self._cell_strat = [[None] * 13 for _ in range(13)]
        for r in range(13):
            for c in range(13):
                for rid in self._cell_rects[r][c][1:]:
                    self._canvas.delete(rid)
                self._cell_rects[r][c] = self._cell_rects[r][c][:1]
                self._canvas.itemconfig(self._cell_rects[r][c][0], fill=COLOR_EMPTY)
                self._canvas.itemconfig(self._cell_texts[r][c], fill="#888888")
                self._canvas.tag_raise(self._cell_texts[r][c])

    def _draw_cell(self, r: int, c: int, strat: dict, actions: list[str]):
        """Draw colored horizontal bands in a cell proportional to action freqs."""
        x1, y1 = c * CELL_SIZE, r * CELL_SIZE
        x2 = x1 + CELL_SIZE - 1
        cell_h = CELL_SIZE - 1

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
