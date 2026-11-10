"""codefinder: detect banned codes, slogans and symbols in text."""

from codefinder.finder import find_codes
from codefinder.normalize import normalize

__all__ = ["find_codes", "normalize"]
