"""Text normalisation: undo the usual tricks used to dodge keyword filters."""

import re
import unicodedata

# Characters that hide or split words without being visible.
_INVISIBLE = [0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF, 0x00AD, 0xFE0F, 0xFE0E]

# Cyrillic and Greek look-alikes -> Latin.
_HOMOGLYPHS = {
    "а": "a",
    "е": "e",
    "о": "o",
    "р": "p",
    "с": "c",
    "х": "x",
    "у": "y",
    "і": "i",
    "ї": "i",
    "к": "k",
    "м": "m",
    "н": "h",
    "т": "t",
    "в": "b",
    "ο": "o",
    "ν": "v",
    "ι": "i",
    "α": "a",
    "ε": "e",
    "ρ": "p",
}

# Ethiopic digits 1-9 (U+1369 to U+1371) -> ASCII digits.
_ETHIOPIC = {0x1369 + i: str(i + 1) for i in range(9)}

_UMLAUTS = {"ä": "ae", "ö": "oe", "ü": "ue"}

# Rare characters (invisible, Ethiopic digits, look-alikes): translated only if present.
_RARE = {
    **dict.fromkeys(_INVISIBLE),
    **_ETHIOPIC,
    **{ord(k): v for k, v in _HOMOGLYPHS.items()},
}
_HAS_RARE = re.compile("[" + "".join(re.escape(chr(c)) for c in _RARE) + "]")

# Leetspeak, used only for word matching (digits stay intact for number codes).
_LEET = {
    "1": "i",
    "!": "i",
    "|": "i",
    "3": "e",
    "4": "a",
    "@": "a",
    "0": "o",
    "5": "s",
    "$": "s",
    "7": "t",
}

# For plain ASCII text: one table that applies leetspeak and drops every non-letter.
_ASCII_LETTERS = {
    i: _LEET.get(chr(i)) for i in range(128) if not ("a" <= chr(i) <= "z")
}

_OBFUSCATED_DIGITS = re.compile("[\uff10-\uff19\u1369-\u1371]")
_REPEATS = re.compile(r"(.)\1+")


def has_obfuscated_digits(text: str) -> bool:
    """True if the raw text uses full-width or Ethiopic digits."""
    return _OBFUSCATED_DIGITS.search(text) is not None


def normalize(text: str) -> str:
    """Lowercase, fold look-alikes, drop invisible characters, spell out umlauts."""
    if text.isascii():
        return text.lower()
    s = unicodedata.normalize("NFKC", text).casefold()
    if _HAS_RARE.search(s):
        s = s.translate(_RARE)
    for char, spelled in _UMLAUTS.items():
        s = s.replace(char, spelled)
    return s


def letters(norm: str) -> str:
    """Word-matching view of a normalised text: leetspeak undone, only a-z kept."""
    if not norm.isascii():
        norm = norm.encode("ascii", "ignore").decode("ascii")
    return norm.translate(_ASCII_LETTERS)


def squash(text: str) -> str:
    """Letters-only view with leetspeak undone and repeated letters collapsed."""
    return _REPEATS.sub(r"\1", letters(normalize(text)))
