"""Selecting parts of a code snippet: by line, by Python token, or by character range.

Everything here is a pure function of the source string. Whatever the author asks for, a selection
resolves to one canonical form, a half-open character range [start, end) into the string. That is the
only thing the evaluator and renderer ever see, so adding a new way to select (a regex, a token kind,
an AST node) means adding one branch to `resolve_selection` and nothing else.
"""

from __future__ import annotations

import io
import keyword
import tokenize
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

TokenKind = Literal["keyword", "name", "number", "string", "op", "comment", "other"]


@dataclass(frozen=True)
class Token:
    kind: TokenKind
    text: str
    start: int  # character offset into the source
    end: int  # exclusive
    line: int  # 1-based line of the token's first character


# Tokens that carry no text worth selecting: layout and end-of-stream markers.
_SKIP = {tokenize.INDENT, tokenize.DEDENT, tokenize.NEWLINE, tokenize.NL, tokenize.ENDMARKER, tokenize.ENCODING}
_KINDS: dict[int, TokenKind] = {
    tokenize.NUMBER: "number",
    tokenize.STRING: "string",
    tokenize.OP: "op",
    tokenize.COMMENT: "comment",
}
for _name in ("FSTRING_START", "FSTRING_MIDDLE", "FSTRING_END"):  # Python 3.12+ splits f-strings into parts
    if hasattr(tokenize, _name):
        _KINDS[getattr(tokenize, _name)] = "string"


@lru_cache(maxsize=256)
def line_ranges(src: str) -> tuple[tuple[int, int], ...]:
    """[start, end) character range of every line, in order, excluding the newline itself."""
    out: list[tuple[int, int]] = []
    start = 0
    for line in src.split("\n"):
        out.append((start, start + len(line)))
        start += len(line) + 1
    return tuple(out)


def line_range(src: str, n: int) -> tuple[int, int]:
    """Character range of line `n` (1-based)."""
    ranges = line_ranges(src)
    if not 1 <= n <= len(ranges):
        raise ValueError(f"line {n} is out of range: the snippet has {len(ranges)} line(s)")
    return ranges[n - 1]


@lru_cache(maxsize=256)
def python_tokens(src: str) -> tuple[Token, ...]:
    """Tokenize `src` with the standard library and convert (row, col) positions to character offsets.

    Cached per source string: the same snippet is resolved once per span per frame during a render.
    Raises ValueError when the snippet is not tokenizable Python (e.g. an unterminated string).
    """
    starts = [r[0] for r in line_ranges(src)]
    out: list[Token] = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type in _SKIP or not tok.string:
                continue
            kind = _KINDS.get(tok.type)
            if kind is None:
                kind = "keyword" if keyword.iskeyword(tok.string) else ("name" if tok.type == tokenize.NAME else "other")
            start = starts[tok.start[0] - 1] + tok.start[1]
            end = starts[tok.end[0] - 1] + tok.end[1]
            out.append(Token(kind, tok.string, start, end, tok.start[0]))
    except (tokenize.TokenError, SyntaxError) as exc:
        raise ValueError(f"cannot tokenize the snippet as Python: {exc}") from None
    return tuple(out)


def resolve_selection(
    src: str,
    *,
    line: int | None = None,
    token: str | None = None,
    nth: int = 0,
    chars: tuple[int, int] | None = None,
) -> tuple[int, int]:
    """Turn a selector into a [start, end) character range of `src`.

    `line` narrows the search to one line (1-based). Then, in order of precedence:
      chars=(a, b)  the half-open range; offsets into the whole snippet, or columns on `line` if given
      token="def"   the nth Python token whose text is exactly that (negative nth counts from the end),
                    searched on `line` if given
      line alone    the whole line, without its newline
    """
    lo, hi = line_range(src, line) if line is not None else (0, len(src))
    where = f"on line {line}" if line is not None else "in the snippet"
    if chars is not None:
        a, b = chars
        if not 0 <= a < b <= hi - lo:
            raise ValueError(f"chars [{a}, {b}] is out of range: {where} there are {hi - lo} characters")
        return lo + a, lo + b
    if token is not None:
        matches = [t for t in python_tokens(src) if t.text == token and lo <= t.start and t.end <= hi]
        if not matches:
            raise ValueError(f"no token {token!r} {where}")
        if not -len(matches) <= nth < len(matches):
            raise ValueError(f"token {token!r} occurs {len(matches)} time(s) {where}; nth={nth} is out of range")
        return matches[nth].start, matches[nth].end
    if line is not None:
        return lo, hi
    raise ValueError("a span needs at least one of: line, token, chars")


__all__ = ["Token", "TokenKind", "line_range", "line_ranges", "python_tokens", "resolve_selection"]
