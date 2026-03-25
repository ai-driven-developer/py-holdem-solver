"""Card representation and deck utilities."""

RANK_CHARS = "23456789TJQKA"
SUIT_CHARS = "cdhs"

RANK_MAP = {c: i for i, c in enumerate(RANK_CHARS)}
SUIT_MAP = {c: i for i, c in enumerate(SUIT_CHARS)}


class Card:
    """A single playing card represented as an integer 0-51."""

    __slots__ = ("_id",)

    def __init__(self, card_str: str):
        rank = RANK_MAP[card_str[0]]
        suit = SUIT_MAP[card_str[1]]
        self._id = rank * 4 + suit

    @classmethod
    def from_id(cls, card_id: int) -> "Card":
        obj = object.__new__(cls)
        obj._id = card_id
        return obj

    @property
    def id(self) -> int:
        return self._id

    @property
    def rank(self) -> int:
        return self._id // 4

    @property
    def suit(self) -> int:
        return self._id % 4

    @property
    def rank_char(self) -> str:
        return RANK_CHARS[self.rank]

    @property
    def suit_char(self) -> str:
        return SUIT_CHARS[self.suit]

    def __repr__(self) -> str:
        return f"{self.rank_char}{self.suit_char}"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Card):
            return self._id == other._id
        return NotImplemented

    def __hash__(self) -> int:
        return self._id

    def __lt__(self, other: "Card") -> bool:
        return self._id < other._id


def parse_cards(s: str) -> list[Card]:
    """Parse a space-separated string of cards, e.g. 'Ah Kd 7s 3c 2h'."""
    return [Card(tok) for tok in s.split()]


def full_deck() -> list[Card]:
    """Return all 52 cards."""
    return [Card.from_id(i) for i in range(52)]


def remaining_deck(excluded: list[Card]) -> list[Card]:
    """Return all cards not in the excluded set."""
    ex = {c.id for c in excluded}
    return [Card.from_id(i) for i in range(52) if i not in ex]
