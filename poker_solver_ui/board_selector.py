"""Visual board card selector – click cards on a 4x13 grid."""

import tkinter as tk
from tkinter import ttk

# Ranks high to low, suits ordered for display
RANKS = list("AKQJT98765432")
SUITS = list("shdc")  # spades, hearts, diamonds, clubs

SUIT_SYMBOLS = {"s": "\u2660", "h": "\u2665", "d": "\u2666", "c": "\u2663"}
SUIT_COLORS = {"s": "#e0e0e0", "h": "#e05555", "d": "#5599ee", "c": "#55bb55"}
SUIT_COLORS_DIM = {"s": "#555555", "h": "#663333", "d": "#335566", "c": "#336633"}

COLOR_BG = "#1a1a1a"
COLOR_CARD_OFF = "#2b2b2b"
COLOR_CARD_BORDER = "#444444"
COLOR_TEXT_OFF = "#666666"

CARD_W = 42
CARD_H = 56
PAD = 2

MAX_BOARD = 5


class BoardSelector(tk.Toplevel):
    """Modal dialog for visually selecting board cards (3-5)."""

    def __init__(self, parent, initial_board: str = ""):
        super().__init__(parent)
        self.title("Select Board Cards")
        self.resizable(False, False)
        self.configure(bg=COLOR_BG)
        self.transient(parent)
        self.grab_set()

        self._result: str | None = None
        # Track selected cards as set of "Rs" strings (e.g. "Ah", "Kd")
        self._selected: list[str] = []
        self._card_rects: dict[str, int] = {}
        self._card_texts: dict[str, int] = {}
        self._card_suit_texts: dict[str, int] = {}

        self._parse_initial(initial_board)
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

    def _parse_initial(self, board_str: str):
        tokens = board_str.strip().split()
        for tok in tokens:
            tok = tok.strip()
            if len(tok) == 2 and tok[0] in "AKQJT98765432" and tok[1] in "shdc":
                if tok not in self._selected:
                    self._selected.append(tok)

    def _build_ui(self):
        # Top info
        top = ttk.Frame(self, padding=4)
        top.pack(fill="x")

        self._info_label = ttk.Label(top, text="")
        self._info_label.pack(side="left", padx=4)

        ttk.Button(top, text="Clear", width=6, command=self._clear).pack(side="right", padx=2)

        # Canvas grid: 4 rows (suits) x 13 cols (ranks)
        cw = 13 * (CARD_W + PAD) + PAD
        ch = 4 * (CARD_H + PAD) + PAD
        self._canvas = tk.Canvas(self, width=cw, height=ch,
                                 bg=COLOR_BG, highlightthickness=0)
        self._canvas.pack(padx=8, pady=4)

        for si, suit in enumerate(SUITS):
            for ri, rank in enumerate(RANKS):
                card_name = f"{rank}{suit}"
                x1 = PAD + ri * (CARD_W + PAD)
                y1 = PAD + si * (CARD_H + PAD)
                x2 = x1 + CARD_W
                y2 = y1 + CARD_H

                is_sel = card_name in self._selected
                fill = SUIT_COLORS[suit] if is_sel else COLOR_CARD_OFF
                outline = SUIT_COLORS[suit] if is_sel else COLOR_CARD_BORDER
                text_fill = "#ffffff" if is_sel else COLOR_TEXT_OFF
                suit_fill = SUIT_COLORS[suit] if not is_sel else "#ffffff"

                rect = self._canvas.create_rectangle(
                    x1, y1, x2, y2, fill=fill, outline=outline, width=1)

                # Rank text (top-left area)
                txt = self._canvas.create_text(
                    x1 + CARD_W // 2, y1 + CARD_H // 2 - 8,
                    text=rank, fill=text_fill,
                    font=("Consolas", 13, "bold"))

                # Suit symbol (below rank)
                suit_txt = self._canvas.create_text(
                    x1 + CARD_W // 2, y1 + CARD_H // 2 + 12,
                    text=SUIT_SYMBOLS[suit], fill=suit_fill,
                    font=("Consolas", 14))

                self._card_rects[card_name] = rect
                self._card_texts[card_name] = txt
                self._card_suit_texts[card_name] = suit_txt

                self._canvas.tag_bind(rect, "<Button-1>",
                                      lambda e, cn=card_name: self._toggle(cn))
                self._canvas.tag_bind(txt, "<Button-1>",
                                      lambda e, cn=card_name: self._toggle(cn))
                self._canvas.tag_bind(suit_txt, "<Button-1>",
                                      lambda e, cn=card_name: self._toggle(cn))

        # Selected cards display
        sel_frame = ttk.Frame(self, padding=4)
        sel_frame.pack(fill="x")

        self._sel_canvas = tk.Canvas(sel_frame, width=cw, height=CARD_H + PAD * 2,
                                     bg=COLOR_BG, highlightthickness=0)
        self._sel_canvas.pack()

        # Bottom buttons
        bottom = ttk.Frame(self, padding=4)
        bottom.pack(fill="x")
        ttk.Button(bottom, text="OK", width=10, command=self._on_ok).pack(side="right", padx=4)
        ttk.Button(bottom, text="Cancel", width=10, command=self._on_cancel).pack(side="right")

        self._update_display()

    def _toggle(self, card_name: str):
        if card_name in self._selected:
            self._selected.remove(card_name)
            self._set_card_visual(card_name, False)
        elif len(self._selected) < MAX_BOARD:
            self._selected.append(card_name)
            self._set_card_visual(card_name, True)
        self._update_display()

    def _set_card_visual(self, card_name: str, selected: bool):
        suit = card_name[1]
        if selected:
            self._canvas.itemconfig(self._card_rects[card_name],
                                    fill=SUIT_COLORS[suit], outline=SUIT_COLORS[suit])
            self._canvas.itemconfig(self._card_texts[card_name], fill="#ffffff")
            self._canvas.itemconfig(self._card_suit_texts[card_name], fill="#ffffff")
        else:
            self._canvas.itemconfig(self._card_rects[card_name],
                                    fill=COLOR_CARD_OFF, outline=COLOR_CARD_BORDER)
            self._canvas.itemconfig(self._card_texts[card_name], fill=COLOR_TEXT_OFF)
            self._canvas.itemconfig(self._card_suit_texts[card_name],
                                    fill=SUIT_COLORS[suit])

    def _update_display(self):
        n = len(self._selected)
        street = ""
        if n == 3:
            street = " (Flop)"
        elif n == 4:
            street = " (Turn)"
        elif n == 5:
            street = " (River)"
        self._info_label.config(text=f"Selected: {n}/{MAX_BOARD}{street}")

        # Redraw selected cards preview
        self._sel_canvas.delete("all")
        preview_w = MAX_BOARD * (CARD_W + PAD * 2) + PAD * 2
        x_start = (int(self._sel_canvas.cget("width")) - preview_w) // 2 + PAD

        for i in range(MAX_BOARD):
            x1 = x_start + i * (CARD_W + PAD * 2)
            y1 = PAD
            x2 = x1 + CARD_W
            y2 = y1 + CARD_H

            if i < n:
                card_name = self._selected[i]
                rank, suit = card_name[0], card_name[1]
                self._sel_canvas.create_rectangle(
                    x1, y1, x2, y2,
                    fill=SUIT_COLORS[suit], outline="#ffffff", width=2)
                self._sel_canvas.create_text(
                    x1 + CARD_W // 2, y1 + CARD_H // 2 - 8,
                    text=rank, fill="#ffffff",
                    font=("Consolas", 13, "bold"))
                self._sel_canvas.create_text(
                    x1 + CARD_W // 2, y1 + CARD_H // 2 + 12,
                    text=SUIT_SYMBOLS[suit], fill="#ffffff",
                    font=("Consolas", 14))
            else:
                self._sel_canvas.create_rectangle(
                    x1, y1, x2, y2,
                    fill=COLOR_CARD_OFF, outline=COLOR_CARD_BORDER, width=1, dash=(3, 3))
                self._sel_canvas.create_text(
                    x1 + CARD_W // 2, y1 + CARD_H // 2,
                    text="?", fill=COLOR_TEXT_OFF,
                    font=("Consolas", 16))

    def _clear(self):
        for card_name in list(self._selected):
            self._set_card_visual(card_name, False)
        self._selected.clear()
        self._update_display()

    def _on_ok(self):
        if len(self._selected) < 3:
            return  # need at least flop
        self._result = " ".join(self._selected)
        self.destroy()

    def _on_cancel(self):
        self._result = None
        self.destroy()
