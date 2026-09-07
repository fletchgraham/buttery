"""Expression AST. Pydantic models are the schema; Python operators build the same tree.

A property value is one of:
  - a number                          (constant)
  - a reference string: "t" or "dot.r"
  - an Op node:    {"op": "mul", "args": [0.2, {"op": "sin", "args": ["t"]}]}
  - a Tween node:  {"op": "tween", "keys": [[0, -3], [1.5, 3]], "ease": "out_cubic"}

Strings that are not bare references are parsed as shorthand ("0.2 * sin(6*t)")
into the same tree. No eval.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Annotated, Any, Iterator, Literal, Optional, Union

from pydantic import BaseModel, BeforeValidator, ConfigDict, Discriminator, Field, Tag, model_validator
from pydantic_core import core_schema

from .color import Color, parse_color
from .easing import Ease
from .ops import ARITY, check_arity

OpName = Literal["add", "sub", "mul", "div", "neg", "sin", "cos", "abs", "min", "max", "clamp", "smoothstep", "noise"]


@dataclass(frozen=True)
class Kind:
    """Field marker: which kind of animatable value a property holds ('number' or 'color')."""

    kind: str


class _Arith:
    """Operator overloading shared by Ref, Op and Tween."""

    def __add__(self, other: Any) -> "Op":
        return Op(op="add", args=[self, other])

    def __radd__(self, other: Any) -> "Op":
        return Op(op="add", args=[other, self])

    def __sub__(self, other: Any) -> "Op":
        return Op(op="sub", args=[self, other])

    def __rsub__(self, other: Any) -> "Op":
        return Op(op="sub", args=[other, self])

    def __mul__(self, other: Any) -> "Op":
        return Op(op="mul", args=[self, other])

    def __rmul__(self, other: Any) -> "Op":
        return Op(op="mul", args=[other, self])

    def __truediv__(self, other: Any) -> "Op":
        return Op(op="div", args=[self, other])

    def __rtruediv__(self, other: Any) -> "Op":
        return Op(op="div", args=[other, self])

    def __neg__(self) -> "Op":
        return Op(op="neg", args=[self])

    def __pos__(self) -> Any:
        return self

    def __abs__(self) -> "Op":
        return Op(op="abs", args=[self])


_REF_RE = re.compile(r"^(t|[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*)$")


class Ref(_Arith):
    """A reference to scene time ("t") or another object's property ("dot.r")."""

    __slots__ = ("path",)

    def __init__(self, path: str) -> None:
        if not isinstance(path, str) or not _REF_RE.match(path):
            raise ValueError(f"invalid reference {path!r}: expected 't' or '<id>.<property>'")
        self.path = path

    @property
    def object_id(self) -> str | None:
        return None if self.path == "t" else self.path.split(".", 1)[0]

    @property
    def prop(self) -> str | None:
        return None if self.path == "t" else self.path.split(".", 1)[1]

    def __repr__(self) -> str:
        return f"Ref({self.path!r})"

    def __str__(self) -> str:
        return self.path

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Ref) and other.path == self.path

    def __hash__(self) -> int:
        return hash(("Ref", self.path))

    @classmethod
    def _validate(cls, v: Any) -> "Ref":
        if isinstance(v, cls):
            return v
        return cls(v)

    @classmethod
    def __get_pydantic_core_schema__(cls, source: Any, handler: Any) -> core_schema.CoreSchema:
        return core_schema.no_info_plain_validator_function(
            cls._validate,
            serialization=core_schema.plain_serializer_function_ser_schema(lambda r: r.path, when_used="always"),
        )

    @classmethod
    def __get_pydantic_json_schema__(cls, cs: Any, handler: Any) -> dict[str, Any]:
        return {
            "type": "string",
            "description": (
                "A reference ('t' for scene time, or '<object id>.<property>'), "
                "or shorthand like '0.2 * sin(6*t)' which parses to the same op tree."
            ),
        }


def _coerce_expr(v: Any) -> Any:
    if isinstance(v, bool):
        raise ValueError("booleans are not valid expression values")
    if isinstance(v, int):
        return float(v)
    if isinstance(v, str):
        from .parse import parse_expr

        return parse_expr(v)
    return v


def _expr_tag(v: Any) -> str | None:
    if isinstance(v, (int, float)):
        return "num"
    if isinstance(v, (str, Ref)):
        return "ref"
    if isinstance(v, Tween):
        return "tween"
    if isinstance(v, Op):
        return "op"
    if isinstance(v, dict):
        return "tween" if v.get("op") == "tween" else "op"
    return None




class Op(_Arith, BaseModel):
    """An operator node: {"op": name, "args": [...]}"""

    model_config = ConfigDict(extra="forbid")

    op: OpName
    args: list["Expr"] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_arity(self) -> "Op":
        check_arity(self.op, len(self.args))
        return self

    def __repr__(self) -> str:
        return f"Op({self.op}, {self.args!r})"

    __str__ = __repr__


KeyValue = Union[float, str]


class Tween(_Arith, BaseModel):
    """Keyframed value. Holds the first/last value outside the key range.

    keys: [[time, value], ...] sorted by time. Values are all numbers or all colors.
    """

    model_config = ConfigDict(extra="forbid")

    op: Literal["tween"] = "tween"
    keys: list[tuple[float, KeyValue]] = Field(min_length=1)
    ease: Ease = "linear"

    @model_validator(mode="after")
    def _check(self) -> "Tween":
        times = [k[0] for k in self.keys]
        if times != sorted(times):
            raise ValueError("tween keys must be sorted by time")
        kinds = {isinstance(k[1], str) for k in self.keys}
        if len(kinds) > 1:
            raise ValueError("tween keys must be all numbers or all colors")
        if kinds == {True}:
            for _, v in self.keys:
                parse_color(v)  # type: ignore[arg-type]
        return self

    @property
    def is_color(self) -> bool:
        return isinstance(self.keys[0][1], str)

    @property
    def start(self) -> float:
        return self.keys[0][0]

    @property
    def end(self) -> float:
        return self.keys[-1][0]

    def __repr__(self) -> str:
        return f"Tween({self.keys!r}, ease={self.ease!r})"

    __str__ = __repr__


Expr = Annotated[
    Union[
        Annotated[float, Tag("num")],
        Annotated[Ref, Tag("ref")],
        Annotated[Op, Tag("op")],
        Annotated[Tween, Tag("tween")],
    ],
    Discriminator(
        _expr_tag,
        custom_error_type="expr_type",
        custom_error_message="expected a number, a reference/expression string, an op node, or a tween node",
    ),
    BeforeValidator(_coerce_expr),
    Kind("number"),
]


def _color_tag(v: Any) -> str | None:
    if isinstance(v, str):
        return "color"
    if isinstance(v, (dict, Tween)):
        return "tween"
    return None


ColorExpr = Annotated[
    Optional[
        Annotated[
            Union[Annotated[Color, Tag("color")], Annotated[Tween, Tag("tween")]],
            Discriminator(
                _color_tag,
                custom_error_type="color_type",
                custom_error_message="expected a color string, a color tween node, or null",
            ),
        ]
    ],
    Kind("color"),
]

Op.model_rebuild()
Tween.model_rebuild()

ExprValue = Union[float, Ref, Op, Tween]
ColorValue = Union[str, Tween, None]


# --------------------------------------------------------------------------- sugar

T = Ref("t")
"""Scene time in seconds."""


def ref(path: str) -> Ref:
    return Ref(path)


def sin(x: Any) -> Op:
    return Op(op="sin", args=[x])


def cos(x: Any) -> Op:
    return Op(op="cos", args=[x])


def min_(*xs: Any) -> Op:
    return Op(op="min", args=list(xs))


def max_(*xs: Any) -> Op:
    return Op(op="max", args=list(xs))


def clamp(x: Any, lo: Any, hi: Any) -> Op:
    return Op(op="clamp", args=[x, lo, hi])


def smoothstep(edge0: Any, edge1: Any, x: Any) -> Op:
    return Op(op="smoothstep", args=[edge0, edge1, x])


def noise(x: Any, seed: Any = None) -> Op:
    return Op(op="noise", args=[x] if seed is None else [x, seed])


def tween(start: KeyValue, end: KeyValue, at: float = 0.0, dur: float = 1.0, ease: Ease = "linear") -> Tween:
    """Tween from `start` to `end`, beginning at time `at` over `dur` seconds."""
    return Tween(keys=[(at, start), (at + dur, end)], ease=ease)


def keyframes(keys: Any, ease: Ease = "linear") -> Tween:
    """Multi-segment tween. `keys` is [(t, v), ...] or {t: v}."""
    if isinstance(keys, dict):
        keys = sorted(keys.items())
    return Tween(keys=list(keys), ease=ease)


# --------------------------------------------------------------------------- introspection


def iter_nodes(expr: Any) -> Iterator[Any]:
    """Depth-first walk over an expression tree (yields floats, Refs, Ops, Tweens)."""
    yield expr
    if isinstance(expr, Op):
        for a in expr.args:
            yield from iter_nodes(a)


def deps(expr: Any) -> set[str]:
    """Reference paths this expression depends on, excluding 't'."""
    return {n.path for n in iter_nodes(expr) if isinstance(n, Ref) and n.path != "t"}


def is_static(expr: Any) -> bool:
    return isinstance(expr, (int, float, str)) or expr is None


__all__ = [
    "ARITY", "Color", "ColorExpr", "ColorValue", "Expr", "ExprValue", "Kind", "Op", "OpName", "Ref",
    "T", "Tween", "clamp", "cos", "deps", "is_static", "iter_nodes", "keyframes", "max_", "min_",
    "noise", "ref", "sin", "smoothstep", "tween",
]
