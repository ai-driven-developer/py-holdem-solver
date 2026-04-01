"""Unified visual strategy viewer — GTO+-style top-down tree + 13×13 strategy grid."""

import tkinter as tk
from tkinter import ttk

RANKS = list("AKQJT98765432")
CELL_SIZE = 42

# Action color palette (GTO+-inspired)
ACTION_COLORS = {
    "f":    "#7a8a7a",   # fold — gray-green
    "x":    "#4caf50",   # check — green
    "c":    "#42a5f5",   # call — blue
    "b33":  "#ffca28",   # small bet — yellow
    "b50":  "#ffa726",   # medium bet — orange
    "b67":  "#ff7043",   # 2/3 pot — deep orange
    "b75":  "#ef5350",   # 3/4 pot — red
    "b100": "#e53935",   # pot — dark red
    "b150": "#c62828",   # 1.5x pot — deep red
    "b200": "#b71c1c",   # 2x pot — darkest red
}
RAISE_COLORS = {
    "r50":  "#ff8a65",
    "r67":  "#ff7043",
    "r75":  "#f4511e",
    "r100": "#e53935",
    "r150": "#c62828",
    "r200": "#b71c1c",
}
ACTION_COLORS.update(RAISE_COLORS)

_FALLBACK_PALETTE = [
    "#ffca28", "#ff7043", "#e53935", "#c62828", "#b71c1c",
    "#42a5f5", "#4caf50", "#7a8a7a", "#7e57c2", "#d4e157",
]

COLOR_EMPTY = "#2b2b2b"
COLOR_GRID_BG = "#1a1a1a"

# ── Tree layout constants (top-down, GTO+ style) ──
TNODE_W = 64
TNODE_H = 28
TNODE_R = 4          # corner radius
TV_GAP = 32          # vertical gap between levels
TH_GAP = 6           # horizontal gap between siblings
TPAD = 12
COLOR_TREE_BG = "#1e1e1e"
COLOR_EDGE = "#555555"
COLOR_ROOT_BG = "#3d3d3d"
COLOR_ROOT_BORDER = "#666666"

# Player badge colors (small indicators, not full node fill)
COLOR_OOP_BADGE = "#ef5350"
COLOR_IP_BADGE = "#42a5f5"


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
    """Short label for a tree node (GTO+ style)."""
    if token == 'x':
        return 'Check'
    if token == 'f':
        return 'Fold'
    if token == 'c':
        return 'Call'
    if token == '|':
        return '\u25b8'
    if token.startswith('b'):
        return f'Bet {token[1:]}%'
    if token.startswith('r'):
        return f'Raise {token[1:]}%'
    return token


class _TreeNode:
    """Node in the unified game-tree trie for graphical layout."""
    __slots__ = ('children', 'spot_idx', 'player', 'label', 'token',
                 'x', 'y', 'width', 'subtree_width', 'expanded', 'action_pct')

    def __init__(self, label: str = "", token: str = ""):
        self.children: dict[str, '_TreeNode'] = {}
        self.spot_idx: int | None = None
        self.player: str = ""          # "OOP" or "IP"
        self.label = label
        self.token = token
        self.x = 0.0
        self.y = 0.0
        self.width = TNODE_W
        self.subtree_width = 0.0
        self.expanded = False
        self.action_pct: float | None = None


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


def _get_node_color(token: str) -> str:
    """Get the background color for a node based on its action (GTO+ style)."""
    if not token:
        return COLOR_ROOT_BG
    if token in ACTION_COLORS:
        return ACTION_COLORS[token]
    # Try to match by prefix + size interpolation
    if token.startswith('b') or token.startswith('r'):
        prefix = token[0]
        try:
            size = float(token[1:])
        except ValueError:
            return COLOR_ROOT_BG
        if prefix == 'b':
            if size <= 40:
                return "#ffca28"
            elif size <= 60:
                return "#ffa726"
            elif size <= 80:
                return "#ff7043"
            elif size <= 110:
                return "#e53935"
            elif size <= 160:
                return "#c62828"
            else:
                return "#b71c1c"
        else:
            if size <= 80:
                return "#ff7043"
            elif size <= 120:
                return "#e53935"
            else:
                return "#c62828"
    return COLOR_ROOT_BG


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
                            result[a] = "#ffca28"
                        elif size <= 60:
                            result[a] = "#ffa726"
                        elif size <= 80:
                            result[a] = "#ff7043"
                        elif size <= 110:
                            result[a] = "#e53935"
                        elif size <= 160:
                            result[a] = "#c62828"
                        else:
                            result[a] = "#b71c1c"
                    else:
                        if size <= 80:
                            result[a] = "#ff7043"
                        elif size <= 120:
                            result[a] = "#e53935"
                        else:
                            result[a] = "#c62828"
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


def _measure_text_width(text: str, font_size: int = 8) -> int:
    """Estimate text width in pixels for a monospace font."""
    return len(text) * (font_size * 0.65) + 16


class StrategyViewer(ttk.Frame):
    """Unified strategy viewer: GTO+-style top-down game tree + 13x13 grid below."""

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
        self.rowconfigure(0, weight=1)    # tree takes available space
        self.rowconfigure(1, weight=0)    # grid is fixed size
        self.columnconfigure(0, weight=1)

        # ── Top: tree panel ──
        tree_frame = ttk.Frame(self)
        tree_frame.grid(row=0, column=0, sticky="nsew")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        self._tree_canvas = tk.Canvas(
            tree_frame, bg=COLOR_TREE_BG, highlightthickness=0, height=200)
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
        self._tree_canvas.bind("<Button-4>",
                               lambda e: self._tree_canvas.yview_scroll(-3, "units"))
        self._tree_canvas.bind("<Button-5>",
                               lambda e: self._tree_canvas.yview_scroll(3, "units"))
        self._tree_canvas.bind("<Shift-Button-4>",
                               lambda e: self._tree_canvas.xview_scroll(-3, "units"))
        self._tree_canvas.bind("<Shift-Button-5>",
                               lambda e: self._tree_canvas.xview_scroll(3, "units"))

        # ── Bottom: grid + legend ──
        bottom_frame = ttk.Frame(self)
        bottom_frame.grid(row=1, column=0, sticky="ew", pady=(4, 0))

        # Player / spot label
        self._player_label = ttk.Label(
            bottom_frame, text="", font=("Consolas", 10, "bold"))
        self._player_label.pack(pady=(4, 2))

        # Grid canvas
        grid_size = 13 * CELL_SIZE
        self._canvas = tk.Canvas(
            bottom_frame, width=grid_size, height=grid_size,
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
        self._legend_frame = ttk.Frame(bottom_frame)
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

    # ── Tree layout (top-down, GTO+ style) ──

    def _measure_node_width(self, node: _TreeNode) -> int:
        """Compute the pixel width needed for a node based on its label."""
        text = node.label
        if node.action_pct is not None:
            text += f" {node.action_pct * 100:.0f}%"
        return max(TNODE_W, int(_measure_text_width(text, 8)))

    def _compute_subtree_widths(self, node: _TreeNode):
        """Post-order: compute subtree width for horizontal spread."""
        node.width = self._measure_node_width(node)
        if not node.children or not node.expanded:
            node.subtree_width = node.width
            return
        for c in node.children.values():
            self._compute_subtree_widths(c)
        children_width = sum(c.subtree_width for c in node.children.values())
        children_width += TH_GAP * max(0, len(node.children) - 1)
        node.subtree_width = max(node.width, children_width)

    def _assign_positions(self, node: _TreeNode, cx: float, top: float):
        """Pre-order: assign positions. cx is the center x of the subtree."""
        node.x = cx - node.width / 2
        node.y = top
        if not node.children or not node.expanded:
            return
        # Distribute children horizontally, centered under this node
        children = list(node.children.values())
        total_w = sum(c.subtree_width for c in children) + TH_GAP * max(0, len(children) - 1)
        child_left = cx - total_w / 2
        child_top = top + TNODE_H + TV_GAP
        for c in children:
            child_cx = child_left + c.subtree_width / 2
            self._assign_positions(c, child_cx, child_top)
            child_left += c.subtree_width + TH_GAP

    def _tree_bounds(self, node: _TreeNode) -> tuple[float, float]:
        """Compute max x, max y of the visible tree."""
        max_x = node.x + node.width
        max_y = node.y + TNODE_H
        if node.expanded:
            for c in node.children.values():
                cx, cy = self._tree_bounds(c)
                max_x = max(max_x, cx)
                max_y = max(max_y, cy)
        return max_x, max_y

    def _tree_min_x(self, node: _TreeNode) -> float:
        """Compute min x of the visible tree."""
        min_x = node.x
        if node.expanded:
            for c in node.children.values():
                min_x = min(min_x, self._tree_min_x(c))
        return min_x

    def _draw_tree(self):
        """Render the full visible tree on the tree canvas."""
        canvas = self._tree_canvas
        canvas.delete("all")
        self._tree_node_items = {}

        if self._tree_root is None:
            return

        self._compute_subtree_widths(self._tree_root)

        # Center the tree horizontally in the canvas
        canvas_w = max(canvas.winfo_width(), 400)
        cx = max(canvas_w / 2, self._tree_root.subtree_width / 2 + TPAD)
        self._assign_positions(self._tree_root, cx, TPAD)

        # Shift everything so min_x >= TPAD
        min_x = self._tree_min_x(self._tree_root)
        if min_x < TPAD:
            self._shift_tree(self._tree_root, TPAD - min_x)

        self._draw_tree_edges(self._tree_root)
        self._draw_tree_nodes(self._tree_root)

        max_x, max_y = self._tree_bounds(self._tree_root)
        canvas.configure(scrollregion=(0, 0, max_x + TPAD, max_y + TPAD))

    def _shift_tree(self, node: _TreeNode, dx: float):
        """Shift all node positions by dx."""
        node.x += dx
        if node.expanded:
            for c in node.children.values():
                self._shift_tree(c, dx)

    def _draw_tree_edges(self, node: _TreeNode):
        if not node.expanded:
            return
        canvas = self._tree_canvas
        parent_cx = node.x + node.width / 2
        parent_bot = node.y + TNODE_H

        for c in node.children.values():
            child_cx = c.x + c.width / 2
            child_top = c.y
            # GTO+ style: vertical line down from parent, then horizontal, then vertical to child
            mid_y = parent_bot + TV_GAP * 0.4
            edge_color = _get_node_color(c.token)
            canvas.create_line(
                parent_cx, parent_bot, parent_cx, mid_y,
                fill=COLOR_EDGE, width=1)
            canvas.create_line(
                parent_cx, mid_y, child_cx, mid_y,
                fill=COLOR_EDGE, width=1)
            canvas.create_line(
                child_cx, mid_y, child_cx, child_top,
                fill=edge_color, width=2)
            self._draw_tree_edges(c)

    def _draw_tree_nodes(self, node: _TreeNode):
        canvas = self._tree_canvas
        x1 = node.x
        y1 = node.y
        x2 = x1 + node.width
        y2 = y1 + TNODE_H

        is_sel = (node is self._current_node)
        has_children = bool(node.children)

        # GTO+ style: color based on action type, not player
        if not node.token:
            # Root node
            fill = "#505050" if not is_sel else "#707070"
            outline = COLOR_ROOT_BORDER
        else:
            fill = _get_node_color(node.token)
            # Brighten if selected
            if is_sel:
                fill = self._brighten(fill, 0.3)
            outline = self._darken(fill, 0.2)

        txt_c = "#ffffff"
        lw = 2 if is_sel else 1

        # Build display text
        display = node.label
        if node.action_pct is not None:
            pct = node.action_pct * 100
            display += f" {pct:.0f}%"

        # Draw rounded rectangle
        r = TNODE_R
        rid = self._draw_rounded_rect(canvas, x1, y1, x2, y2, r,
                                       fill=fill, outline=outline, width=lw)

        tid = canvas.create_text(
            (x1 + x2) / 2, (y1 + y2) / 2,
            text=display, fill=txt_c, font=("Consolas", 8, "bold"))

        # Player indicator — small colored dot on the left
        if node.player:
            dot_color = COLOR_OOP_BADGE if node.player == "OOP" else COLOR_IP_BADGE
            dot_r = 3
            canvas.create_oval(
                x1 + 4, (y1 + y2) / 2 - dot_r,
                x1 + 4 + dot_r * 2, (y1 + y2) / 2 + dot_r,
                fill=dot_color, outline="")

        # Expand/collapse indicator
        if has_children:
            indicator = "\u25bc" if node.expanded else "\u25b6"
            canvas.create_text(
                x2 - 8, (y1 + y2) / 2,
                text=indicator, fill="#cccccc", font=("Consolas", 6))

        for item_id in rid:
            self._tree_node_items[item_id] = node
        self._tree_node_items[tid] = node

        # Draw children if expanded
        if node.expanded:
            for c in node.children.values():
                self._draw_tree_nodes(c)

    def _draw_rounded_rect(self, canvas, x1, y1, x2, y2, r, **kwargs):
        """Draw a rounded rectangle, return list of item ids."""
        points = [
            x1 + r, y1,
            x2 - r, y1,
            x2, y1,
            x2, y1 + r,
            x2, y2 - r,
            x2, y2,
            x2 - r, y2,
            x1 + r, y2,
            x1, y2,
            x1, y2 - r,
            x1, y1 + r,
            x1, y1,
            x1 + r, y1,
        ]
        item = canvas.create_polygon(points, smooth=True, **kwargs)
        return [item]

    @staticmethod
    def _brighten(hex_color: str, factor: float) -> str:
        """Make a hex color brighter."""
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        r = min(255, int(r + (255 - r) * factor))
        g = min(255, int(g + (255 - g) * factor))
        b = min(255, int(b + (255 - b) * factor))
        return f"#{r:02x}{g:02x}{b:02x}"

    @staticmethod
    def _darken(hex_color: str, factor: float) -> str:
        """Make a hex color darker."""
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        r = max(0, int(r * (1 - factor)))
        g = max(0, int(g * (1 - factor)))
        b = max(0, int(b * (1 - factor)))
        return f"#{r:02x}{g:02x}{b:02x}"

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
            if clicked_node.children:
                clicked_node.expanded = not clicked_node.expanded
        else:
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
