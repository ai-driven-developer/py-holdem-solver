"""Visual 13x13 range selector widget for poker hand ranges."""

import tkinter as tk
from tkinter import ttk

# Ranks from high to low (display order)
RANKS = list("AKQJT98765432")

# Color scheme
COLOR_PAIR = "#4a90d9"
COLOR_SUITED = "#d94a4a"
COLOR_OFFSUIT = "#49a349"
COLOR_OFF = "#2b2b2b"
COLOR_HOVER = "#555555"
COLOR_TEXT = "#ffffff"
COLOR_TEXT_OFF = "#888888"

CELL_SIZE = 38


def _cell_label(row: int, col: int) -> str:
    """Return the hand name for a cell in the 13x13 matrix."""
    if row == col:
        return f"{RANKS[row]}{RANKS[col]}"
    elif row < col:
        return f"{RANKS[row]}{RANKS[col]}s"
    else:
        return f"{RANKS[col]}{RANKS[row]}o"


def _cell_type(row: int, col: int) -> str:
    if row == col:
        return "pair"
    elif row < col:
        return "suited"
    else:
        return "offsuit"


def _active_color(row: int, col: int) -> str:
    t = _cell_type(row, col)
    if t == "pair":
        return COLOR_PAIR
    elif t == "suited":
        return COLOR_SUITED
    else:
        return COLOR_OFFSUIT


class RangeSelector(tk.Toplevel):
    """Modal dialog with a 13x13 clickable range grid."""

    def __init__(self, parent, title: str, initial_range: str = ""):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._result: str | None = None
        self._selected: list[list[bool]] = [[False] * 13 for _ in range(13)]
        self._rects: list[list[int]] = [[0] * 13 for _ in range(13)]
        self._texts: list[list[int]] = [[0] * 13 for _ in range(13)]
        self._drag_mode: bool | None = None  # True=selecting, False=deselecting

        self._parse_initial(initial_range)
        self._build_ui()

        # Center on parent
        self.update_idletasks()
        px = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{max(0, px)}+{max(0, py)}")

        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.wait_window()

    @property
    def result(self) -> str | None:
        return self._result

    def _parse_initial(self, range_str: str):
        """Parse a range string and mark matching cells as selected."""
        if not range_str.strip():
            return
        tokens = [t.strip() for t in range_str.split(",")]
        for token in tokens:
            hands = self._expand_token(token)
            for hand in hands:
                r, c = self._hand_to_cell(hand)
                if r is not None:
                    self._selected[r][c] = True

    def _expand_token(self, token: str) -> list[str]:
        """Expand a range token into individual hand names."""
        token = token.strip()
        if not token:
            return []

        rank_idx = {c: i for i, c in enumerate(RANKS)}

        # Range: JJ-99 or ATs-A2s
        if "-" in token:
            left, right = token.split("-", 1)
            left, right = left.strip(), right.strip()
            r1l = rank_idx.get(left[0])
            r2l = rank_idx.get(left[1]) if len(left) > 1 else None
            r1r = rank_idx.get(right[0])
            r2r = rank_idx.get(right[1]) if len(right) > 1 else None
            if None in (r1l, r2l, r1r, r2r):
                return []

            suffix = ""
            if left[-1] in "so":
                suffix = left[-1]

            # Pair range
            if r1l == r2l and r1r == r2r:
                lo, hi = min(r1l, r1r), max(r1l, r1r)
                return [f"{RANKS[r]}{RANKS[r]}" for r in range(lo, hi + 1)]

            # Unpaired range
            results = []
            lo, hi = min(r2l, r2r), max(r2l, r2r)
            for r in range(lo, hi + 1):
                if r == r1l:
                    continue
                high_r = min(r1l, r)  # min index = higher rank
                low_r = max(r1l, r)
                name = f"{RANKS[high_r]}{RANKS[low_r]}"
                if suffix:
                    name += suffix
                results.append(name)
            return results

        # Plus notation
        has_plus = token.endswith("+")
        base = token.rstrip("+")
        if len(base) < 2:
            return []

        r1 = rank_idx.get(base[0])
        r2 = rank_idx.get(base[1])
        if r1 is None or r2 is None:
            return []

        suffix = ""
        if len(base) > 2 and base[2] in "so":
            suffix = base[2]

        # Pair
        if r1 == r2:
            if has_plus:
                return [f"{RANKS[r]}{RANKS[r]}" for r in range(0, r1 + 1)]
            return [f"{RANKS[r1]}{RANKS[r2]}"]

        # Ensure high card first (lower index = higher rank)
        if r1 > r2:
            r1, r2 = r2, r1

        if has_plus:
            results = []
            for r in range(r1 + 1, r2 + 1):
                name = f"{RANKS[r1]}{RANKS[r]}"
                if suffix:
                    name += suffix
                results.append(name)
            return results

        name = f"{RANKS[r1]}{RANKS[r2]}"
        if suffix:
            name += suffix
        return [name]

    def _hand_to_cell(self, hand: str) -> tuple[int | None, int | None]:
        """Convert a hand name like 'AKs' to (row, col) in the matrix."""
        rank_idx = {c: i for i, c in enumerate(RANKS)}
        if len(hand) < 2:
            return None, None
        r1 = rank_idx.get(hand[0])
        r2 = rank_idx.get(hand[1])
        if r1 is None or r2 is None:
            return None, None

        suffix = hand[2] if len(hand) > 2 else ""

        if r1 == r2:
            return r1, r2
        elif suffix == "s":
            # Suited: above diagonal, row = higher rank (lower index)
            return min(r1, r2), max(r1, r2)
        elif suffix == "o":
            # Offsuit: below diagonal, row = lower rank (higher index)
            return max(r1, r2), min(r1, r2)
        else:
            # No suffix: select both suited and offsuit
            hi, lo = min(r1, r2), max(r1, r2)
            self._selected[hi][lo] = True  # suited
            return lo, hi  # offsuit

    def _build_ui(self):
        top = ttk.Frame(self, padding=4)
        top.pack(fill="x")

        ttk.Button(top, text="All", width=6, command=self._select_all).pack(side="left", padx=2)
        ttk.Button(top, text="Clear", width=6, command=self._clear_all).pack(side="left", padx=2)
        ttk.Button(top, text="Pairs", width=6, command=self._select_pairs).pack(side="left", padx=2)
        ttk.Button(top, text="Suited", width=6, command=self._select_suited).pack(side="left", padx=2)
        ttk.Button(top, text="Broadway", width=8, command=self._select_broadway).pack(side="left", padx=2)

        # Percentage label
        self._pct_label = ttk.Label(top, text="0.0%")
        self._pct_label.pack(side="right", padx=8)
        ttk.Label(top, text="Selected:").pack(side="right")

        # Canvas for the grid
        size = 13 * CELL_SIZE
        self._canvas = tk.Canvas(self, width=size, height=size,
                                 bg="#1a1a1a", highlightthickness=0)
        self._canvas.pack(padx=8, pady=(4, 4))

        for r in range(13):
            for c in range(13):
                x1, y1 = c * CELL_SIZE, r * CELL_SIZE
                x2, y2 = x1 + CELL_SIZE - 1, y1 + CELL_SIZE - 1
                color = _active_color(r, c) if self._selected[r][c] else COLOR_OFF
                text_color = COLOR_TEXT if self._selected[r][c] else COLOR_TEXT_OFF
                rect = self._canvas.create_rectangle(
                    x1, y1, x2, y2, fill=color, outline="#1a1a1a", width=1)
                label = _cell_label(r, c)
                txt = self._canvas.create_text(
                    (x1 + x2) // 2, (y1 + y2) // 2,
                    text=label, fill=text_color,
                    font=("Consolas", 9, "bold"))
                self._rects[r][c] = rect
                self._texts[r][c] = txt

        self._canvas.bind("<ButtonPress-1>", self._on_press)
        self._canvas.bind("<B1-Motion>", self._on_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_release)

        # Bottom buttons
        bottom = ttk.Frame(self, padding=4)
        bottom.pack(fill="x")
        ttk.Button(bottom, text="OK", width=10, command=self._on_ok).pack(side="right", padx=4)
        ttk.Button(bottom, text="Cancel", width=10, command=self._on_cancel).pack(side="right")

        self._update_pct()

    def _cell_at(self, x: int, y: int) -> tuple[int, int] | None:
        col = x // CELL_SIZE
        row = y // CELL_SIZE
        if 0 <= row < 13 and 0 <= col < 13:
            return row, col
        return None

    def _on_press(self, event):
        cell = self._cell_at(event.x, event.y)
        if cell is None:
            return
        r, c = cell
        self._drag_mode = not self._selected[r][c]
        self._toggle_cell(r, c, self._drag_mode)

    def _on_drag(self, event):
        if self._drag_mode is None:
            return
        cell = self._cell_at(event.x, event.y)
        if cell is None:
            return
        r, c = cell
        if self._selected[r][c] != self._drag_mode:
            self._toggle_cell(r, c, self._drag_mode)

    def _on_release(self, _event):
        self._drag_mode = None

    def _toggle_cell(self, r: int, c: int, state: bool):
        self._selected[r][c] = state
        if state:
            self._canvas.itemconfig(self._rects[r][c], fill=_active_color(r, c))
            self._canvas.itemconfig(self._texts[r][c], fill=COLOR_TEXT)
        else:
            self._canvas.itemconfig(self._rects[r][c], fill=COLOR_OFF)
            self._canvas.itemconfig(self._texts[r][c], fill=COLOR_TEXT_OFF)
        self._update_pct()

    def _update_pct(self):
        total = 0
        for r in range(13):
            for c in range(13):
                if self._selected[r][c]:
                    t = _cell_type(r, c)
                    if t == "pair":
                        total += 6
                    elif t == "suited":
                        total += 4
                    else:
                        total += 12
        # Total possible combos: C(52,2) = 1326
        pct = total / 1326 * 100
        self._pct_label.config(text=f"{pct:.1f}%")

    def _set_all(self, state: bool):
        for r in range(13):
            for c in range(13):
                self._toggle_cell(r, c, state)

    def _select_all(self):
        self._set_all(True)

    def _clear_all(self):
        self._set_all(False)

    def _select_pairs(self):
        for r in range(13):
            self._toggle_cell(r, r, True)

    def _select_suited(self):
        for r in range(13):
            for c in range(r + 1, 13):
                self._toggle_cell(r, c, True)

    def _select_broadway(self):
        """Select all broadway hands (T+)."""
        broadway = range(0, 5)  # A, K, Q, J, T
        for r in broadway:
            for c in broadway:
                self._toggle_cell(r, c, True)

    def _build_range_string(self) -> str:
        """Convert selected cells to a compact range string."""
        parts = []
        for r in range(13):
            for c in range(13):
                if self._selected[r][c]:
                    parts.append(_cell_label(r, c))
        return ",".join(parts)

    def _on_ok(self):
        self._result = self._build_range_string()
        self.destroy()

    def _on_cancel(self):
        self._result = None
        self.destroy()
