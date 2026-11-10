"""Find banned codes, slogans and symbols in text, driven by config/codes.csv.

All patterns are compiled once per config file. Each text is normalised once and
most texts are rejected by a cheap pre-check before any rule is tried.
"""

import csv
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from codefinder.normalize import has_obfuscated_digits, letters, normalize, squash

DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "config" / "codes.csv"
_WORD = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class NumericRule:
    """A number code that only counts with a context word next to it."""

    code: str
    pattern: re.Pattern[str]
    loose: frozenset[str]
    strict: frozenset[str]


@dataclass(frozen=True)
class RuleSet:
    """Everything compiled from one config file."""

    order: dict[str, int]
    phrase_any: re.Pattern[str] | None
    phrases: tuple[tuple[str, re.Pattern[str]], ...]
    numeric: tuple[NumericRule, ...]
    numeric_hint: tuple[str, ...]
    emoji_first: re.Pattern[str] | None
    emoji: tuple[tuple[str, tuple[str, ...]], ...]


def _phrase_pattern(phrase: str) -> re.Pattern[str]:
    """Regex over the letters-only view; every letter may repeat (stretched words)."""
    collapsed = squash(phrase)
    return re.compile("".join(re.escape(c) + "+" for c in collapsed))


@lru_cache(maxsize=4)
def load_rules(path: str) -> RuleSet:
    """Read a UTF-8 CSV with columns code,kind,value,context and compile it."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    order: dict[str, int] = {}
    phrases: list[tuple[str, re.Pattern[str]]] = []
    numeric: list[NumericRule] = []
    emoji: list[tuple[str, tuple[str, ...]]] = []
    for r in rows:
        code, kind, value, context = (
            r[k].strip() for k in ("code", "kind", "value", "context")
        )
        order.setdefault(code, len(order))
        if kind == "phrase":
            phrases.extend((code, _phrase_pattern(p)) for p in value.split("|"))
        elif kind == "numeric":
            words = [w for w in context.split("|") if w]
            numeric.append(
                NumericRule(
                    code,
                    re.compile(value),
                    frozenset(w for w in words if not w.startswith("^")),
                    frozenset(w[1:] for w in words if w.startswith("^")),
                )
            )
        elif kind == "emoji":
            emoji.append((code, tuple(normalize(p) for p in value.split("|"))))
        else:
            raise ValueError(f"unknown rule kind: {kind}")
    any_phrase = (
        re.compile("|".join(p.pattern for _, p in phrases)) if phrases else None
    )
    hint = tuple(sorted({w for n in numeric for w in n.loose | n.strict}))
    firsts = sorted({seq[0] for _, seqs in emoji for seq in seqs})
    first_re = re.compile("[" + re.escape("".join(firsts)) + "]") if firsts else None
    return RuleSet(
        order, any_phrase, tuple(phrases), tuple(numeric), hint, first_re, tuple(emoji)
    )


def _numeric_hit(rule: NumericRule, norm: str) -> bool:
    for m in rule.pattern.finditer(norm):
        before = _WORD.findall(norm, 0, m.start())
        after = _WORD.findall(norm, m.end())
        if rule.loose.intersection(before[-2:] + after[:3]) or rule.strict.intersection(
            before[-1:]
        ):
            return True
    return False


def find_codes(text: str, config_path: str | None = None) -> list[str]:
    """Return the names of all codes found in text (empty list if none)."""
    path = config_path or os.environ.get("CODEFINDER_CONFIG") or str(DEFAULT_CONFIG)
    rules = load_rules(path)
    norm = normalize(text)
    found: set[str] = set()

    # Word codes: one pre-check on the letters-only view, then each phrase on a hit.
    if rules.phrase_any is not None:
        view = letters(norm)
        if rules.phrase_any.search(view):
            found.update(code for code, pat in rules.phrases if pat.search(view))

    # Number codes: need a context word next to the number (or obfuscated digits).
    if rules.numeric:
        obfuscated = has_obfuscated_digits(text)
        if obfuscated or any(w in norm for w in rules.numeric_hint):
            for rule in rules.numeric:
                if (
                    rule.code not in found
                    and rule.pattern.search(norm)
                    and (obfuscated or _numeric_hit(rule, norm))
                ):
                    found.add(rule.code)

    # Emoji sequences: only if one of the first emoji appears.
    if rules.emoji_first is not None and rules.emoji_first.search(norm):
        flat = norm.replace(" ", "")
        found.update(code for code, seqs in rules.emoji if any(s in flat for s in seqs))

    return sorted(found, key=rules.order.__getitem__)
