"""Shorthand expression parser: "0.2 * sin(6*t) + dot.r" -> AST. No eval.

Grammar:
    expr    := term (('+' | '-') term)*
    term    := unary (('*' | '/') unary)*
    unary   := '-' unary | primary
    primary := NUMBER | IDENT | IDENT '(' expr (',' expr)* ')' | '(' expr ')'
    IDENT   := name | name '.' name      (name = [A-Za-z_][A-Za-z0-9_]*)

Functions: sin cos abs min max clamp smoothstep noise. Constants: pi, tau.
Constant sub-expressions are folded.
"""

from __future__ import annotations

import math
import re
from typing import Any

from .ops import ARITY, OP_FUNCS, check_arity

_TOKEN = re.compile(
    r"\s*(?:(?P<num>\d+\.\d*(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?|\d+(?:[eE][+-]?\d+)?)"
    r"|(?P<ident>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?)"
    r"|(?P<punct>[-+*/(),]))"
)

_CONSTANTS = {"pi": math.pi, "tau": math.tau}
_FUNCS = {"sin", "cos", "abs", "min", "max", "clamp", "smoothstep", "noise"}


def _tokenize(src: str) -> list[tuple[str, str, int]]:
    tokens: list[tuple[str, str, int]] = []
    pos = 0
    n = len(src)
    while pos < n:
        m = _TOKEN.match(src, pos)
        if not m or m.end() == pos:
            rest = src[pos:].lstrip()
            if not rest:
                break
            raise ValueError(f"unexpected character {rest[0]!r} at position {pos} in {src!r}")
        pos = m.end()
        kind = m.lastgroup
        if kind is None:
            continue
        tokens.append((kind, m.group(kind), m.start(kind)))
    return tokens


def _mk(op: str, args: list[Any]) -> Any:
    """Build an Op, folding constants when every arg is a number."""
    from .expr import Op

    check_arity(op, len(args))
    if all(isinstance(a, float) for a in args):
        try:
            return float(OP_FUNCS[op](*args))
        except (ZeroDivisionError, ValueError, OverflowError):
            pass
    return Op(op=op, args=args)


class _Parser:
    def __init__(self, src: str) -> None:
        self.src = src
        self.tokens = _tokenize(src)
        self.i = 0

    def peek(self) -> tuple[str, str, int] | None:
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def take(self, kind: str | None = None, value: str | None = None) -> tuple[str, str, int]:
        tok = self.peek()
        if tok is None:
            raise ValueError(f"unexpected end of expression in {self.src!r}")
        if (kind is not None and tok[0] != kind) or (value is not None and tok[1] != value):
            want = value or kind
            raise ValueError(f"expected {want!r} but found {tok[1]!r} at position {tok[2]} in {self.src!r}")
        self.i += 1
        return tok

    def parse(self) -> Any:
        if not self.tokens:
            raise ValueError("empty expression")
        node = self.expr()
        if self.peek() is not None:
            tok = self.peek()
            assert tok is not None
            raise ValueError(f"unexpected {tok[1]!r} at position {tok[2]} in {self.src!r}")
        return node

    def expr(self) -> Any:
        node = self.term()
        while (tok := self.peek()) and tok[0] == "punct" and tok[1] in "+-":
            self.i += 1
            rhs = self.term()
            node = _mk("add" if tok[1] == "+" else "sub", [node, rhs])
        return node

    def term(self) -> Any:
        node = self.unary()
        while (tok := self.peek()) and tok[0] == "punct" and tok[1] in "*/":
            self.i += 1
            rhs = self.unary()
            node = _mk("mul" if tok[1] == "*" else "div", [node, rhs])
        return node

    def unary(self) -> Any:
        tok = self.peek()
        if tok and tok[0] == "punct" and tok[1] == "-":
            self.i += 1
            return _mk("neg", [self.unary()])
        if tok and tok[0] == "punct" and tok[1] == "+":
            self.i += 1
            return self.unary()
        return self.primary()

    def primary(self) -> Any:
        from .expr import Ref

        tok = self.take()
        kind, text, pos = tok
        if kind == "num":
            return float(text)
        if kind == "punct" and text == "(":
            node = self.expr()
            self.take("punct", ")")
            return node
        if kind == "ident":
            nxt = self.peek()
            if nxt and nxt[0] == "punct" and nxt[1] == "(":
                if text not in _FUNCS:
                    raise ValueError(f"unknown function {text!r} at position {pos}; known: {', '.join(sorted(_FUNCS))}")
                self.i += 1
                args = [self.expr()]
                while (t2 := self.peek()) and t2[0] == "punct" and t2[1] == ",":
                    self.i += 1
                    args.append(self.expr())
                self.take("punct", ")")
                return _mk(text, args)
            if text in _CONSTANTS:
                return _CONSTANTS[text]
            if "." in text or text == "t":
                return Ref(text)
            raise ValueError(
                f"unknown name {text!r} at position {pos}: use 't', '<id>.<property>', pi, tau, or a number"
            )
        raise ValueError(f"unexpected {text!r} at position {pos} in {self.src!r}")


def parse_expr(src: str) -> Any:
    """Parse shorthand into a float, Ref, or Op. Raises ValueError with position info."""
    return _Parser(src).parse()


__all__ = ["parse_expr"]
