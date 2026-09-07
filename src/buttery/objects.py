"""Scene primitives. Every animatable property is an Expr (number or expression tree)."""

from __future__ import annotations

from typing import Annotated, Any, ClassVar, Iterator, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

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
        return [n for n in cls.model_fields if n not in anim and n not in ("id", "type", "children")]

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
    """Text anchored at (x, y). `size` is the font size in world units."""

    type: Literal["text"] = "text"
    content: str = ""
    x: Expr = 0.0
    y: Expr = 0.0
    size: Expr = 0.5
    fill: ColorExpr = "white"
    font: str | None = Field(default=None, description="Font family name, e.g. 'Helvetica'. Null = system default.")
    align: Literal["left", "center", "right"] = "center"


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


AnyObject = Annotated[Union[Circle, Rect, Line, Text, Group], Field(discriminator="type")]

Group.model_rebuild()

OBJECT_TYPES: dict[str, type[SceneObject]] = {"circle": Circle, "rect": Rect, "line": Line, "text": Text, "group": Group}


def walk(objects: list[SceneObject], path: str = "objects") -> Iterator[tuple[SceneObject, str]]:
    """Depth-first (obj, json_path) over a tree of objects."""
    for i, obj in enumerate(objects):
        p = f"{path}[{i}]"
        yield obj, p
        if isinstance(obj, Group):
            yield from walk(obj.children, f"{p}.children")


__all__ = ["AnyObject", "Circle", "Group", "Line", "OBJECT_TYPES", "Rect", "SceneObject", "Text", "walk"]
