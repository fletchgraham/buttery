"""MCP server exposing the four tools. Run with `buttery mcp` (stdio)."""

from __future__ import annotations

import base64
import json
from typing import Any

from mcp.server.mcpserver import Image, MCPServer

from . import tools
from .scene import Scene

INSTRUCTIONS = """\
2D explainer animations where the scene is a pure function of time.

Workflow: write scene JSON -> validate -> preview at a few t values -> render.
Coordinates: world units, origin at center, y up, the frame is `view_width` (default 8) units wide
(so x runs -4..4 and, at 16:9, y runs -2.25..2.25). Colors are hex or CSS names.

Scene: {"duration": 5, "fps": 60, "size": [1920,1080], "background": "#111111", "objects": [...]}
Objects (each needs a unique "id" and a "type"):
  circle: x y r fill stroke stroke_width opacity
  rect:   x y w h corner_radius rotation fill stroke stroke_width opacity   (x,y = center; rotation in degrees CCW)
  line:   x1 y1 x2 y2 stroke stroke_width opacity
  text:   content(static) font(static) align(static: left|center|right) x y size fill opacity
  code:   content font char_width line_height theme spans[] (static) x y size fill opacity
          monospace block, top-left at (x,y), fixed grid (0.6*size per column); theme "default" highlights Python
  span:   only inside code.spans; selectors line / token (+nth) / chars (static), then fill background opacity
  group:  x y rotation scale opacity children[]

Any numeric property can be: a number, "t", "<id>.<prop>", a shorthand string like "0.2*sin(6*t)",
an op node {"op": "mul", "args": [...]} (ops: add sub mul div neg sin cos abs min max clamp smoothstep noise),
or a tween {"op": "tween", "keys": [[0, -3], [1.5, 3]], "ease": "out_cubic"}
(eases: linear in_quad out_quad in_out_quad out_cubic in_out_cubic spring; holds first/last outside the keys).
Colors (fill/stroke) can be a color string, null, or a tween whose key values are colors.
Errors name the object id, property and t. Read the scene://schema resource for the full JSON schema.
"""

server = MCPServer("buttery", instructions=INSTRUCTIONS)


def _scene_arg(scene: dict[str, Any] | str) -> dict[str, Any] | str:
    return scene


@server.tool(description="Validate scene JSON. Returns ok or structured errors (path, message, object, property).")
def validate(scene: dict[str, Any] | str) -> dict[str, Any]:
    return tools.validate(_scene_arg(scene))


@server.tool(description="Resolve every property of the scene at time t (seconds). Plain data, no expressions.")
def state(scene: dict[str, Any] | str, t: float) -> dict[str, Any]:
    return tools.state(_scene_arg(scene), t)


@server.tool(description="Render a single low-res PNG at time t (no motion blur). scale is relative to scene size.")
def preview(scene: dict[str, Any] | str, t: float = 0.0, scale: float = 0.25) -> Image | dict[str, Any]:
    result = tools.preview(_scene_arg(scene), t, scale)
    if not result["ok"]:
        return result
    return Image(data=base64.b64decode(result["png_base64"]), format="png")


@server.tool(description="Render the full animation to path (.mp4/.mov via ffmpeg, or a directory of PNG frames).")
def render(
    scene: dict[str, Any] | str,
    path: str,
    motion_blur: bool = True,
    samples: int = 8,
    workers: int | None = None,
) -> dict[str, Any]:
    return tools.render(_scene_arg(scene), path, motion_blur=motion_blur, samples=samples, workers=workers)


@server.resource("scene://schema", name="Scene JSON schema", mime_type="application/json")
def scene_schema() -> str:
    return json.dumps(Scene.json_schema(), indent=2)


def run() -> None:
    server.run("stdio")


if __name__ == "__main__":
    run()
