"""Easing curves. Each maps progress p in [0, 1] to eased progress."""

from __future__ import annotations

import math
from typing import Callable, Literal, get_args

Ease = Literal["linear", "in_quad", "out_quad", "in_out_quad", "out_cubic", "in_out_cubic", "spring"]
EASE_NAMES: tuple[str, ...] = get_args(Ease)


def linear(p: float) -> float:
    return p


def in_quad(p: float) -> float:
    return p * p


def out_quad(p: float) -> float:
    return 1.0 - (1.0 - p) ** 2


def in_out_quad(p: float) -> float:
    return 2.0 * p * p if p < 0.5 else 1.0 - (-2.0 * p + 2.0) ** 2 / 2.0


def out_cubic(p: float) -> float:
    return 1.0 - (1.0 - p) ** 3


def in_out_cubic(p: float) -> float:
    return 4.0 * p**3 if p < 0.5 else 1.0 - (-2.0 * p + 2.0) ** 3 / 2.0


_SPRING_OMEGA = 12.0
_SPRING_ZETA = 0.55
_SPRING_OMEGA_D = _SPRING_OMEGA * math.sqrt(1.0 - _SPRING_ZETA**2)


def spring(p: float) -> float:
    """Underdamped spring settling on 1. Overshoots ~10% then settles."""
    if p >= 1.0:
        return 1.0
    if p <= 0.0:
        return 0.0
    decay = math.exp(-_SPRING_ZETA * _SPRING_OMEGA * p)
    wd = _SPRING_OMEGA_D * p
    return 1.0 - decay * (math.cos(wd) + (_SPRING_ZETA * _SPRING_OMEGA / _SPRING_OMEGA_D) * math.sin(wd))


EASINGS: dict[str, Callable[[float], float]] = {
    "linear": linear,
    "in_quad": in_quad,
    "out_quad": out_quad,
    "in_out_quad": in_out_quad,
    "out_cubic": out_cubic,
    "in_out_cubic": in_out_cubic,
    "spring": spring,
}
