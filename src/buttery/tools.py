"""The agent tool surface: validate / state / preview / render.

Every function takes scene JSON (dict or string) and returns a JSON-able dict:
    {"ok": true, ...} or {"ok": false, "errors": [{"path", "message", "object"?, "property"?, "t"?}]}
Never a bare stack trace.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any, Callable

from .errors import EvalError, RenderError, SceneError, SceneValidationError
from .scene import Scene

SceneInput = dict[str, Any] | str | bytes | Scene


def _load(scene: SceneInput) -> Scene:
    if isinstance(scene, Scene):
        return scene
    return Scene.from_json(scene)


def _fail(errors: list[SceneError]) -> dict[str, Any]:
    return {"ok": False, "errors": [e.to_dict() for e in errors]}


def _guard(fn: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    try:
        return fn()
    except SceneValidationError as exc:
        return _fail(exc.errors)
    except EvalError as exc:
        return _fail([exc.error])
    except RenderError as exc:
        return _fail([SceneError(path="render", message=str(exc))])
    except Exception as exc:  # noqa: BLE001 - last resort, still structured
        return _fail([SceneError(path="scene", message=f"internal error: {type(exc).__name__}: {exc}")])


def validate(scene: SceneInput) -> dict[str, Any]:
    """Structural (schema) + semantic (ids, references, cycles) validation."""

    def run() -> dict[str, Any]:
        s = _load(scene)
        return {
            "ok": True,
            "objects": [o.id for o, _ in s],
            "duration": s.duration,
            "fps": s.fps,
            "frames": s.frame_count,
            "size": list(s.size),
        }

    return _guard(run)


def state(scene: SceneInput, t: float) -> dict[str, Any]:
    """Every property resolved at time t."""

    def run() -> dict[str, Any]:
        s = _load(scene)
        return {"ok": True, **s.state(float(t))}

    return _guard(run)


def preview(scene: SceneInput, t: float = 0.0, scale: float = 0.25, path: str | None = None) -> dict[str, Any]:
    """Single low-res PNG (base64) at time t. Optionally also written to `path`."""

    def run() -> dict[str, Any]:
        s = _load(scene)
        png = s.preview(float(t), scale=float(scale), path=path)
        w, h = (max(1, round(d * scale)) for d in s.size)
        out: dict[str, Any] = {"ok": True, "t": float(t), "width": w, "height": h, "png_base64": base64.b64encode(png).decode()}
        if path:
            out["path"] = str(Path(path))
        return out

    return _guard(run)


def render(
    scene: SceneInput,
    path: str,
    motion_blur: bool = True,
    samples: int = 8,
    shutter: float = 0.5,
    workers: int | None = None,
) -> dict[str, Any]:
    """Render to .mp4/.mov or a PNG-sequence directory."""

    def run() -> dict[str, Any]:
        s = _load(scene)
        result = s.render(path, motion_blur=motion_blur, samples=samples, shutter=shutter, workers=workers)
        return {"ok": True, **result.to_dict()}

    return _guard(run)


def schema() -> dict[str, Any]:
    """JSON schema of the Scene document (the product contract)."""
    return Scene.json_schema()


def to_json(result: dict[str, Any]) -> str:
    return json.dumps(result, indent=2)


__all__ = ["preview", "render", "schema", "state", "validate"]
