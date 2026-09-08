"""Scene primitives. Every animatable property is an Expr (number or expression tree)."""

from __future__ import annotations

from typing import Annotated, Any, ClassVar, Iterator, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .code import Token, python_tokens, resolve_selection
from .expr import ColorExpr, Expr, Kind, Ref

_ID_PATTERN = r"^[A-Za-z_][A-Za-z0-9_]*$"


class _RefProxy:
    """`obj.ref.x` -> Ref("obj.x"). Only animatable properties are allowed."""

    def __init__(self, owner: "SceneObject") -> None:
        self._owner = owner

    def __getattr__(self, name: str) -> Ref:
        kinds = type(self._owner).animatable()
        if name not in kinds:
            raise AttributeError(
                f"'{self._owner.type}' has no animatable property {name!r}; available: {', '.join(kinds)}"
            )
        if kinds[name] != "number":
            raise AttributeError(f"cannot reference {name!r}: only numeric properties can be referenced")
        return Ref(f"{self._owner.id}.{name}")


class SceneObject(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    id: str = Field(pattern=_ID_PATTERN, description="Unique id, used in references like 'dot.x'.")
    opacity: Expr = 1.0

    def __init__(self, id: str | None = None, /, **data: Any) -> None:
        if id is not None:
            data["id"] = id
        super().__init__(**data)

    @property
    def ref(self) -> _RefProxy:
        return _RefProxy(self)

    _animatable_cache: ClassVar[dict[str, str] | None] = None

    @classmethod
    def animatable(cls) -> dict[str, str]:
        """Animatable property name -> kind ('number' | 'color')."""
        if cls.__dict__.get("_animatable_cache") is None:
            out: dict[str, str] = {}
            for name, field in cls.model_fields.items():
                for meta in field.metadata:
                    if isinstance(meta, Kind):
                        out[name] = meta.kind
            cls._animatable_cache = out
        return cls._animatable_cache  # type: ignore[return-value]

    @classmethod
    def static_props(cls) -> list[str]:
        anim = cls.animatable()
        return [n for n in cls.model_fields if n not in anim and n not in ("id", "type", "children", "spans")]

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.id!r})"


class Circle(SceneObject):
    type: Literal["circle"] = "circle"
    x: Expr = 0.0
    y: Expr = 0.0
    r: Expr = 0.5
    fill: ColorExpr = "white"
    stroke: ColorExpr = None
    stroke_width: Expr = 0.05


class Rect(SceneObject):
    """Axis-aligned rectangle centered on (x, y); `rotation` in degrees, counter-clockwise."""

    type: Literal["rect"] = "rect"
    x: Expr = 0.0
    y: Expr = 0.0
    w: Expr = 1.0
    h: Expr = 1.0
    corner_radius: Expr = 0.0
    fill: ColorExpr = "white"
    stroke: ColorExpr = None
    stroke_width: Expr = 0.05
    rotation: Expr = 0.0


class Line(SceneObject):
    type: Literal["line"] = "line"
    x1: Expr = -1.0
    y1: Expr = 0.0
    x2: Expr = 1.0
    y2: Expr = 0.0
    stroke: ColorExpr = "white"
    stroke_width: Expr = 0.05


class Text(SceneObject):
    """Text anchored at (x, y). `size` is the font size in world units.

    Newlines in `content` start new lines; `max_width` wraps long lines at word boundaries. A multi-line
    block is centered vertically on `y`, so a single line sits exactly where it did before.
    """

    type: Literal["text"] = "text"
    content: str = ""
    x: Expr = 0.0
    y: Expr = 0.0
    size: Expr = 0.5
    fill: ColorExpr = "white"
    font: str | None = Field(default=None, description="Font family name, e.g. 'Helvetica'. Null = system default.")
    align: Literal["left", "center", "right"] = "center"
    max_width: float | None = Field(
        default=None, gt=0, description="Wrap at this width in world units (word boundaries). Null = never wrap."
    )
    line_height: float = Field(default=1.25, gt=0, description="Line spacing as a multiple of `size`.")


class Span(SceneObject):
    """A selection inside a `Code` block: the selected characters get their own fill, background and opacity.

    Which characters (see `code.resolve_selection`): `line` narrows to one 1-based line, then
      chars=[a, b]   a half-open character range (offsets into the snippet, or columns on `line`)
      token="def"    the nth Python token with exactly that text; `nth` counts from 0, negative from the end
      line alone     the whole line
    A null `fill` keeps the code's fill. `opacity` multiplies the opacity of the characters it covers (like a
    group's does for its children), so a per-line reveal and a later highlight compose. `background` paints the
    covered cells. Spans apply in order: where two set `fill`, the later one wins.
    """

    type: Literal["span"] = "span"
    line: int | None = Field(default=None, ge=1)
    token: str | None = None
    nth: int = 0
    chars: tuple[int, int] | None = None
    fill: ColorExpr = None
    background: ColorExpr = None

    @model_validator(mode="after")
    def _has_selector(self) -> "Span":
        if self.line is None and self.token is None and self.chars is None:
            raise ValueError("a span needs at least one of: line, token, chars")
        return self


class Code(SceneObject):
    """A monospace code block anchored at its top-left corner (x, y). `size` is the font size in world units.

    Characters sit on a fixed grid: column c of row r is at (x + c * char_width * size, y - r * line_height * size).
    The grid, not the font, decides the layout, so positions are the same on every machine and can be computed
    without a renderer (`width`, `height`). `spans` style parts of the snippet; `select()` is the sugar for adding one.
    Only `token` selection needs the snippet to be valid Python; `line` and `chars` work on any text.
    """

    type: Literal["code"] = "code"
    content: str = ""
    x: Expr = 0.0
    y: Expr = 0.0
    size: Expr = 0.3
    fill: ColorExpr = "white"
    font: str | None = Field(default=None, description="Monospace family name. Null = Menlo / Consolas / DejaVu Sans Mono / Courier.")
    char_width: float = Field(default=0.6, gt=0, description="Column pitch as a multiple of `size` (0.6 matches most monospace fonts).")
    line_height: float = Field(default=1.4, gt=0, description="Row pitch as a multiple of `size`.")
    spans: list[Span] = Field(default_factory=list)

    @field_validator("content")
    @classmethod
    def _no_tabs(cls, v: str) -> str:
        if "\t" in v:
            raise ValueError("use spaces, not tabs: the grid is one character per column")
        return v

    def select(self, id: str, **spec: Any) -> Span:
        """Add a span. `line`, `token`, `nth`, `chars` pick the characters; the rest are Span properties."""
        span = Span(id, **spec)
        self.span_range(span)  # fail now, with a clear message, rather than at Scene time
        self.spans.append(span)
        return span

    def span_range(self, span: Span) -> tuple[int, int]:
        """The [start, end) character range a span selects. Raises ValueError if it does not resolve."""
        return resolve_selection(self.content, line=span.line, token=span.token, nth=span.nth, chars=span.chars)

    def tokens(self) -> tuple[Token, ...]:
        return python_tokens(self.content)

    @property
    def rows(self) -> int:
        return self.content.count("\n") + 1

    @property
    def cols(self) -> int:
        return max(len(line) for line in self.content.split("\n"))

    @property
    def width(self) -> Any:
        """Block width in world units. An expression if `size` is one, so `code.x = -code.width / 2` centers it."""
        return self.cols * self.char_width * self.size

    @property
    def height(self) -> Any:
        return self.rows * self.line_height * self.size


class Group(SceneObject):
    """Transforms children: translate(x, y), rotate (degrees), uniform scale, opacity."""

    type: Literal["group"] = "group"
    x: Expr = 0.0
    y: Expr = 0.0
    rotation: Expr = 0.0
    scale: Expr = 1.0
    children: list["AnyObject"] = Field(default_factory=list)

    def add(self, *objs: "SceneObject") -> "Group":
        self.children.extend(objs)
        return self


AnyObject = Annotated[Union[Circle, Rect, Line, Text, Code, Group], Field(discriminator="type")]

Group.model_rebuild()

OBJECT_TYPES: dict[str, type[SceneObject]] = {
    "circle": Circle, "rect": Rect, "line": Line, "text": Text, "code": Code, "span": Span, "group": Group,
}


def walk(objects: list[SceneObject], path: str = "objects") -> Iterator[tuple[SceneObject, str]]:
    """Depth-first (obj, json_path) over a tree of objects."""
    for i, obj in enumerate(objects):
        p = f"{path}[{i}]"
        yield obj, p
        if isinstance(obj, Group):
            yield from walk(obj.children, f"{p}.children")
        elif isinstance(obj, Code):
            yield from walk(obj.spans, f"{p}.spans")


__all__ = ["AnyObject", "Circle", "Code", "Group", "Line", "OBJECT_TYPES", "Rect", "SceneObject", "Span", "Text", "walk"]
