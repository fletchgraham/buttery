"""Scene: the top-level document. `state(t)` is a pure function of time."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterator

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from pydantic_core import PydanticCustomError

from .color import Color
from .errors import SceneError, SceneValidationError, errors_from_validation
from .expr import Op, Ref, Tween, iter_nodes
from .objects import AnyObject, Code, Group, SceneObject, walk

if TYPE_CHECKING:
    from .evaluate import CompiledScene
    from .render import RenderResult


class Scene(BaseModel):
    """A 2D scene. World units, origin at center, y up; the view spans `view_width` units."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    size: tuple[int, int] = Field(default=(1920, 1080), description="Output size in pixels (width, height).")
    fps: int = Field(default=60, ge=1, le=240)
    duration: float = Field(gt=0, description="Length in seconds.")
    background: Color = "#111111"
    view_width: float = Field(default=8.0, gt=0, description="How many world units span the frame width.")
    objects: list[AnyObject] = Field(default_factory=list)

    # ------------------------------------------------------------------ authoring

    def add(self, *objs: SceneObject) -> "Scene":
        self.objects.extend(objs)
        return self

    def __iter__(self) -> Iterator[tuple[SceneObject, str]]:  # type: ignore[override]
        return walk(self.objects)

    def find(self, object_id: str) -> SceneObject:
        for obj, _ in walk(self.objects):
            if obj.id == object_id:
                return obj
        raise KeyError(object_id)

    @property
    def frame_count(self) -> int:
        return max(1, round(self.duration * self.fps))

    @property
    def px_per_unit(self) -> float:
        return self.size[0] / self.view_width

    # ------------------------------------------------------------------ JSON

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(self.model_dump(mode="json"), indent=indent)

    def save(self, path: str | Path) -> Path:
        p = Path(path)
        p.write_text(self.to_json())
        return p

    @classmethod
    def from_json(cls, data: str | bytes | dict[str, Any]) -> "Scene":
        """Build a Scene from JSON text or a dict. Raises SceneValidationError with structured errors."""
        if isinstance(data, (str, bytes)):
            try:
                data = json.loads(data)
            except json.JSONDecodeError as exc:
                raise SceneValidationError([SceneError(path="scene", message=f"invalid JSON: {exc}")]) from None
        try:
            return cls.model_validate(data)
        except ValidationError as exc:
            raise SceneValidationError(errors_from_validation(exc, data)) from None

    @classmethod
    def load(cls, path: str | Path) -> "Scene":
        return cls.from_json(Path(path).read_text())

    @classmethod
    def json_schema(cls) -> dict[str, Any]:
        return cls.model_json_schema()

    # ------------------------------------------------------------------ validation

    @model_validator(mode="after")
    def _semantic(self) -> "Scene":
        errors = self.check()
        if errors:
            raise PydanticCustomError(
                "scene",
                "{n} scene error(s): {first}",
                {"n": len(errors), "first": str(errors[0]), "errors": [e.to_dict() for e in errors]},
            )
        return self

    def check(self) -> list[SceneError]:
        """Semantic validation: unique ids, span selectors resolve, references resolve, no cycles, tween kinds match."""
        errors: list[SceneError] = []
        by_id: dict[str, SceneObject] = {}
        paths: dict[str, str] = {}

        for obj, path in walk(self.objects):
            if obj.id in by_id:
                errors.append(SceneError(path=f"{path}.id", message=f"duplicate id {obj.id!r} (also at {paths[obj.id]})", object=obj.id, property="id"))
            else:
                by_id[obj.id] = obj
                paths[obj.id] = path

        for obj, path in walk(self.objects):
            if isinstance(obj, Code):
                for j, span in enumerate(obj.spans):
                    try:
                        obj.span_range(span)
                    except ValueError as exc:
                        errors.append(SceneError(path=f"{path}.spans[{j}]", message=str(exc), object=span.id))

        edges: dict[str, set[str]] = {}
        for obj, path in walk(self.objects):
            kinds = type(obj).animatable()
            for prop, kind in kinds.items():
                expr = getattr(obj, prop)
                key = f"{obj.id}.{prop}"
                ppath = f"{path}.{prop}"
                edges[key] = set()
                for node in iter_nodes(expr):
                    if isinstance(node, Tween):
                        if kind == "color" and not node.is_color:
                            errors.append(SceneError(path=ppath, message="tween on a color property needs color keys, e.g. [[0, \"red\"], [1, \"blue\"]]", object=obj.id, property=prop))
                        elif kind == "number" and node.is_color:
                            errors.append(SceneError(path=ppath, message="tween on a numeric property needs numeric keys", object=obj.id, property=prop))
                    elif isinstance(node, Ref) and node.path != "t":
                        target_id, target_prop = node.object_id, node.prop
                        assert target_id and target_prop
                        target = by_id.get(target_id)
                        if target is None:
                            errors.append(SceneError(path=ppath, message=f"reference {node.path!r}: no object with id {target_id!r}", object=obj.id, property=prop))
                            continue
                        tkinds = type(target).animatable()
                        if target_prop not in tkinds:
                            errors.append(SceneError(path=ppath, message=f"reference {node.path!r}: {target.type} {target_id!r} has no animatable property {target_prop!r}; available: {', '.join(tkinds)}", object=obj.id, property=prop))
                        elif tkinds[target_prop] != "number":
                            errors.append(SceneError(path=ppath, message=f"reference {node.path!r}: only numeric properties can be referenced", object=obj.id, property=prop))
                        else:
                            edges[key].add(node.path)

        cycle = _find_cycle(edges)
        if cycle:
            first = cycle[0]
            obj_id, prop = first.split(".", 1)
            errors.append(SceneError(path=f"{paths.get(obj_id, obj_id)}.{prop}", message="dependency cycle: " + " -> ".join(cycle + [first]), object=obj_id, property=prop))
        return errors

    # ------------------------------------------------------------------ evaluation

    def compile(self) -> "CompiledScene":
        from .evaluate import CompiledScene

        return CompiledScene(self)

    def state(self, t: float) -> dict[str, Any]:
        """Resolve every property at time t. Plain data, no expressions."""
        return self.compile().state(t)

    # ------------------------------------------------------------------ rendering

    def preview(self, t: float = 0.0, scale: float = 0.25, path: str | Path | None = None) -> bytes:
        """Single low-res PNG at time t (no motion blur). Returns PNG bytes; also writes `path` if given."""
        from .render import preview

        return preview(self, t, scale=scale, path=path)

    def render(self, path: str | Path, **options: Any) -> "RenderResult":
        """Render to .mp4/.mov (via ffmpeg) or a PNG sequence directory. See render.render()."""
        from .render import render

        return render(self, path, **options)


def _find_cycle(edges: dict[str, set[str]]) -> list[str] | None:
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {k: WHITE for k in edges}
    stack: list[str] = []

    def visit(node: str) -> list[str] | None:
        color[node] = GRAY
        stack.append(node)
        for nxt in sorted(edges.get(node, ())):
            if nxt not in color:
                continue
            if color[nxt] == GRAY:
                return stack[stack.index(nxt) :]
            if color[nxt] == WHITE:
                found = visit(nxt)
                if found:
                    return found
        stack.pop()
        color[node] = BLACK
        return None

    for k in sorted(edges):
        if color[k] == WHITE:
            found = visit(k)
            if found:
                return found
    return None


__all__ = ["Scene"]
