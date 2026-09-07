"""Numeric implementations of the expression ops. Pure functions on floats."""

from __future__ import annotations

import math
from typing import Callable

# op name -> (min args, max args or None for variadic)
ARITY: dict[str, tuple[int, int | None]] = {
    "add": (2, None),
    "sub": (2, 2),
    "mul": (2, None),
    "div": (2, 2),
    "neg": (1, 1),
    "sin": (1, 1),
    "cos": (1, 1),
    "abs": (1, 1),
    "min": (2, None),
    "max": (2, None),
    "clamp": (3, 3),
    "smoothstep": (3, 3),
    "noise": (1, 2),
}


def _add(*xs: float) -> float:
    return math.fsum(xs)


def _sub(a: float, b: float) -> float:
    return a - b


def _mul(*xs: float) -> float:
    out = 1.0
    for x in xs:
        out *= x
    return out


def _div(a: float, b: float) -> float:
    if b == 0.0:
        raise ZeroDivisionError("division by zero")
    return a / b


def _neg(x: float) -> float:
    return -x


def _clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def _smoothstep(e0: float, e1: float, x: float) -> float:
    if e0 == e1:
        return 0.0 if x < e0 else 1.0
    p = _clamp((x - e0) / (e1 - e0), 0.0, 1.0)
    return p * p * (3.0 - 2.0 * p)


def _hash01(i: int, seed: int) -> float:
    x = (i * 374761393 + seed * 668265263) & 0xFFFFFFFF
    x = ((x ^ (x >> 13)) * 1274126177) & 0xFFFFFFFF
    x ^= x >> 16
    return x / 0xFFFFFFFF


def _noise(x: float, seed: float = 0.0) -> float:
    """Deterministic 1D value noise in [-1, 1], smooth, period-free."""
    s = int(seed)
    i = math.floor(x)
    f = x - i
    a = _hash01(i, s)
    b = _hash01(i + 1, s)
    u = f * f * (3.0 - 2.0 * f)
    return (a + (b - a) * u) * 2.0 - 1.0


OP_FUNCS: dict[str, Callable[..., float]] = {
    "add": _add,
    "sub": _sub,
    "mul": _mul,
    "div": _div,
    "neg": _neg,
    "sin": math.sin,
    "cos": math.cos,
    "abs": abs,
    "min": min,
    "max": max,
    "clamp": _clamp,
    "smoothstep": _smoothstep,
    "noise": _noise,
}


def check_arity(op: str, n: int) -> None:
    lo, hi = ARITY[op]
    if n < lo or (hi is not None and n > hi):
        if hi is None:
            want = f"at least {lo}"
        elif lo == hi:
            want = str(lo)
        else:
            want = f"{lo} to {hi}"
        raise ValueError(f"'{op}' takes {want} argument(s), got {n}")
