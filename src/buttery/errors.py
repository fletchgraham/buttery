"""Structured errors. Every error names a path, and where possible the object id, property and t."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from pydantic import ValidationError


@dataclass
class SceneError:
    path: str
    message: str
    object: str | None = None
    property: str | None = None
    t: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}

    def __str__(self) -> str:
        where = self.path
        if self.object:
            where += f" (object '{self.object}'" + (f", property '{self.property}'" if self.property else "") + ")"
        if self.t is not None:
            where += f" at t={self.t:g}"
        return f"{where}: {self.message}"


class SceneValidationError(ValueError):
    """Raised when a scene fails structural or semantic validation."""

    def __init__(self, errors: list[SceneError]) -> None:
        self.errors = errors
        super().__init__("\n".join(str(e) for e in errors))


class EvalError(RuntimeError):
    """Raised when an expression fails at evaluation time."""

    def __init__(self, object_id: str, prop: str, t: float, message: str) -> None:
        self.error = SceneError(path=f"{object_id}.{prop}", message=message, object=object_id, property=prop, t=t)
        super().__init__(str(self.error))


class RenderError(RuntimeError):
    """Raised when rasterization or encoding fails."""


_TAGS = {"circle", "rect", "line", "text", "group", "num", "ref", "op", "tween", "color"}


def _clean_loc(loc: tuple[Any, ...], raw: Any) -> tuple[tuple[Any, ...], str | None, str | None]:
    """Drop union-branch tag segments from loc (they are not keys in the input).

    Returns (clean loc, nearest enclosing object id, property under that object).
    """
    clean: list[Any] = []
    obj_id: str | None = None
    prop: str | None = None
    node = raw
    for part in loc:
        if isinstance(node, dict):
            if isinstance(node.get("id"), str):
                obj_id, prop = node["id"], None
            if part in node:
                if obj_id is not None and prop is None and part != "children":
                    prop = str(part)
                node = node[part]
            elif part in _TAGS:
                continue
            else:
                node = None
        elif isinstance(node, list) and isinstance(part, int) and part < len(node):
            node = node[part]
        elif part in _TAGS:
            continue
        else:
            node = None
        clean.append(part)
    if isinstance(node, dict) and isinstance(node.get("id"), str):
        obj_id, prop = node["id"], None
    return tuple(clean), obj_id, prop


def _loc_to_path(loc: tuple[Any, ...]) -> str:
    out = ""
    for part in loc:
        if isinstance(part, int):
            out += f"[{part}]"
        else:
            out += ("." if out else "") + str(part)
    return out


def errors_from_validation(exc: ValidationError, raw: Any = None) -> list[SceneError]:
    out: list[SceneError] = []
    for err in exc.errors(include_url=False):
        ctx = err.get("ctx") or {}
        if isinstance(ctx.get("errors"), list):  # semantic errors bundled by Scene's validator
            out.extend(SceneError(**e) if isinstance(e, dict) else e for e in ctx["errors"])
            continue
        loc = tuple(err.get("loc", ()))
        msg = err.get("msg", "invalid value")
        if msg.startswith("Value error, "):
            msg = msg[len("Value error, ") :]
        loc, obj_id, prop = _clean_loc(loc, raw)
        out.append(SceneError(path=_loc_to_path(loc) or "scene", message=msg, object=obj_id, property=prop))
    # de-duplicate (unions can report the same problem once per branch)
    seen: set[tuple[str, str]] = set()
    unique: list[SceneError] = []
    for e in out:
        key = (e.path, e.message)
        if key not in seen:
            seen.add(key)
            unique.append(e)
    return unique


__all__ = ["EvalError", "RenderError", "SceneError", "SceneValidationError", "errors_from_validation"]
