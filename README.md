<p align="center">
  <img src="https://raw.githubusercontent.com/fletchgraham/buttery/main/docs/logo.png" alt="" width="260">
</p>

<h1 align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/fletchgraham/buttery/main/docs/wordmark-dark.png">
    <img src="https://raw.githubusercontent.com/fletchgraham/buttery/main/docs/wordmark.png" alt="buttery" width="220">
  </picture>
</h1>

<p align="center">Buttery smooth, agent-friendly explainer animations in Python.</p>

```
❯ Use buttery to make an animated explainer of merging two sorted lists.
```

![Merging two sorted lists, one comparison per beat](https://raw.githubusercontent.com/fletchgraham/buttery/main/examples/merge_sorted.gif)

*`examples/merge_sorted.py`: the merge is simulated in Python, then each step becomes keyframes.*

## Key features

- **The scene is a pure function of time.** `state(t)` resolves every property at `t`. Nothing accumulates
  between frames, so every frame renders independently and in parallel, and a scrub to any `t` is exact.
- **Pydantic models are the schema.** JSON is the product contract; the Python API is sugar over the same
  models. `buttery schema` prints the JSON schema an agent can build against.
- **Properties are expressions, not values.** Tweens, keyframes, `sin(6 * T)`, and references to other
  objects' properties (`ring.x = dot.ref.x`) form a dependency DAG, so edges follow nodes for free.
  Shorthand strings like `"dot.r + 0.5"` parse into the same tree, no `eval`.
- **Built for agents.** `validate` / `state` / `preview` / `render` as a CLI, a Python API, and an MCP server.
  Every call returns `{"ok": true, ...}` or a structured error list, never a bare stack trace. A Claude Code
  skill is included.
- **Explainer primitives.** `circle rect line text group`, and a `code` block that syntax-highlights Python and
  lets spans select by token, line, or character range.
- **Validation up front.** Structural checks from pydantic (unknown fields, arity, colors) plus semantic checks:
  unique ids, references resolve, no dependency cycles.
- **Real motion blur.** A skia-python renderer samples sub-frames across a configurable shutter, uses every
  core, and writes an `.mp4` through ffmpeg or a PNG sequence without it.

## More examples

```
❯ Use buttery to show a red-black tree left rotation one step at a time.
```

![Red-black tree left rotation, one step at a time](https://raw.githubusercontent.com/fletchgraham/buttery/main/examples/rb_rotation.gif)

*`examples/rb_rotation.py`: nodes are groups, edges are lines whose endpoints reference the nodes, so the
edges follow the rotation for free. The before/after trees are two tuples; the script diffs them.*

```
❯ Use buttery to show every token color of the syntax highlighter, one kind per beat.
```

![Every color of the syntax highlighter, side by side](https://raw.githubusercontent.com/fletchgraham/buttery/main/examples/syntax_theme.gif)

*`examples/syntax_theme.py`: a custom `theme` colors all six token kinds; the legend walks them one per beat and
every token of that kind pulses in the code.*

## Architecture

```
Agent tool surface   validate / state / preview / render     (tools.py, cli.py, mcp_server.py)
Authoring            Python sugar  <->  JSON                 (objects.py, expr.py, parse.py)
Core                 Scene, primitives, expression DAG       (scene.py, evaluate.py)
Renderer             skia-python, motion blur via sub-frames  (render.py)
```

## Install

```bash
pip install buttery    # or: uv add buttery
brew install ffmpeg    # for .mp4 output (PNG sequences work without it)
```

The renderer is skia-python, which ships large platform wheels; expect a heavier install than the code size suggests.

From a clone:

```bash
uv sync                # Python 3.11+, pydantic, skia-python, numpy, mcp
uv run pytest
```

## Python

```python
from buttery import *

dot = Circle("dot", r=0.3, fill="coral")
dot.x = tween(-3, 3, at=0, dur=1.5, ease="out_cubic")
dot.y = 0.2 * sin(6 * T)

ring = Circle("ring", fill=None, stroke="white")
ring.x = dot.ref.x
ring.r = dot.ref.r + 0.5

scene = Scene(duration=3).add(dot, ring, Text("label", content="Hello", y=-1.6))
scene.state(1.0)                       # plain data
scene.preview(1.0, path="p.png")       # quick low-res PNG
scene.render("out.mp4")                # motion blur, all cores, ffmpeg
scene.save("scene.json")               # the same thing as JSON
```

`obj.prop` reads the stored expression; `obj.ref.prop` makes a reference to it (the spec's `dot.r + 0.5`
became `dot.ref.r + 0.5` because a plain attribute read cannot be both a value and a reference).

## JSON

```json
{
  "duration": 3,
  "objects": [
    {"id": "dot", "type": "circle", "r": 0.3, "fill": "coral",
     "x": {"op": "tween", "keys": [[0, -3], [1.5, 3]], "ease": "out_cubic"},
     "y": {"op": "mul", "args": [0.2, {"op": "sin", "args": [{"op": "mul", "args": [6, "t"]}]}]}},
    {"id": "ring", "type": "circle", "fill": null, "stroke": "white", "x": "dot.x", "r": "dot.r + 0.5"}
  ]
}
```

Shorthand strings like `"dot.r + 0.5"` parse (no `eval`) into the same op tree. `uv run buttery schema`
prints the JSON schema from `Scene.model_json_schema()`.

**Coordinates**: world units, origin at center, y up. The frame is `view_width` (default 8) units wide.
**Primitives**: `circle rect line text code group`. `text` wraps at `max_width` and honors newlines. `code` is a
monospace block on a fixed character grid; its `spans` select characters by `line`, by Python `token`, or by
`chars` range and give them their own `fill`, `background` and `opacity`; `theme: "default"` (or a kind -> color
mapping) syntax-highlights Python tokens. **Ops**: `add sub mul div neg sin cos abs min max clamp smoothstep noise`.
**Eases**: `linear in_quad out_quad in_out_quad out_cubic in_out_cubic spring`. Colors: hex or CSS names;
`fill`/`stroke` can be tweened between colors.

## Agent surface

```bash
uv run buttery validate scene.json
uv run buttery state scene.json --t 1.25
uv run buttery preview scene.json --t 1.25 --out p.png --scale 0.25
uv run buttery render scene.json out.mp4 [--no-motion-blur --samples 8 --shutter 0.5 --workers N]
uv run buttery mcp            # MCP server on stdio: same four tools + scene://schema resource
```

Every call returns `{"ok": true, ...}` or `{"ok": false, "errors": [{"path", "message", "object", "property", "t"}]}`.
Never a bare stack trace.

Claude Code skill: `skill/` (symlink or copy it into `~/.claude/skills/buttery`). Register the MCP server with
`claude mcp add buttery -- uv run --directory /path/to/this/repo buttery mcp`.
Or from the published packages, no checkout needed: `claude mcp add buttery -- npx -y buttery-mcp`
(the [`buttery-mcp`](https://www.npmjs.com/package/buttery-mcp) npm shim runs `uvx buttery mcp`; see `npm/`).

## Validation and evaluation rules

- Structural validation is pydantic (unknown fields rejected, arity checked, colors checked).
- Semantic validation: unique ids (global across groups), references resolve to numeric animatable
  properties, no dependency cycles, tween key kinds match the property kind.
- Evaluation compiles each expression to a closure once, walks the DAG in dependency order, and never mutates the scene.
- Motion blur: `samples` sub-frames spread across `shutter` × frame interval, averaged (0.5 = 180° shutter).

## Layout

```
src/buttery/
  expr.py        AST models (Op, Tween, Ref), operator overloading, sugar (T, sin, tween, keyframes, ...)
  parse.py       shorthand parser -> AST, constant folding
  objects.py     Circle, Rect, Line, Text, Code (+ Span), Group
  code.py        Python tokenizer, line / token / chars selection -> character ranges, highlight themes
  scene.py       Scene, semantic checks, state(t)
  evaluate.py    compile + topological evaluation
  render.py      skia rasterizer, motion blur, parallel render, ffmpeg
  tools.py       validate / state / preview / render (JSON in, JSON out)
  cli.py         `buttery` command
  mcp_server.py  MCP server
examples/        bounce.py, squash_bounce.py, merge_sorted.py, rb_rotation.py, code_walk.py, syntax_theme.py (Python) and their .json, launch_demo.json
skill/           Claude Code skill
tests/
```

## Not in v1

Equations/LaTeX, 3D or cameras, GUI, audio, plugins, manim parity.
