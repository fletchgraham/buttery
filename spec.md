# Explainer Animation Library — v1 Spec

Working name: TBD.

## Purpose

A Python library for 2D explainer animations where the scene is a pure function of time and the primary author may be an AI agent. Human-elegant to write, JSON-native for agents, buttery output.

## Core Principle

`state(t)` is a pure function. Nothing accumulates between frames. Every frame renders independently and in parallel.

## Architecture

```
┌──────────────────────────────┐
│  Agent tool surface          │  validate / state / preview / render
├──────────────────────────────┤
│  Authoring                   │  Python sugar  ⇄  JSON (same pydantic models)
├──────────────────────────────┤
│  Core                        │  Scene, primitives, expression graph, state(t)
├──────────────────────────────┤
│  Renderer                    │  skia-python: state(t) → frame; motion blur via sub-frames
└──────────────────────────────┘
```

Schema first. Pydantic models *are* the schema. Python API is derived sugar over them; the JSON form is the product contract.

## Scene

```
Scene
  size: (w, h)        default (1920, 1080)
  fps: int            default 60
  duration: seconds
  background: color
  objects: list[Object]
```

Coordinate space: world units, origin at center, y up. Default view spans ~8 units wide.

## Primitives (v1 only)

| Type      | Properties (all animatable unless noted)                          |
|-----------|-------------------------------------------------------------------|
| `circle`  | x, y, r, fill, stroke, stroke_width, opacity                      |
| `rect`    | x, y, w, h, corner_radius, fill, stroke, stroke_width, opacity, rotation |
| `line`    | x1, y1, x2, y2, stroke, stroke_width, opacity                     |
| `text`    | content (static), x, y, size, fill, opacity, font (static)        |
| `group`   | x, y, rotation, scale, opacity, children                          |

Every object has a unique `id` (string). Colors are hex or named.

## Animated Properties

Each animatable property is a **value or an expression**. Constants are the trivial case.

### Expression AST

A property's value is a tree. Leaves are numbers or references; nodes are ops.

```json
{"op": "mul", "args": [0.2, {"op": "sin", "args": [{"op": "mul", "args": [6, "t"]}]}]}
```

References:
- `"t"` — scene time in seconds
- `"circle1.r"` — another object's property (DAG, cycles rejected at validation)

Ops (v1 vocabulary, keep small):
- arithmetic: `add sub mul div neg`
- math: `sin cos abs min max clamp`
- shaping: `smoothstep noise`
- timing: `tween` (see below)

Python builds the same tree via operator overloading:

```python
dot.y = 0.2 * sin(6 * T)
ring.r = dot.r + 0.5
```

### Keyframes / tween

The workhorse for agents. A `tween` node:

```json
{"op": "tween", "keys": [[0.0, -3], [1.5, 3]], "ease": "out_cubic"}
```

- `keys`: list of `[time, value]`, sorted
- `ease`: `linear | in_quad | out_quad | in_out_quad | out_cubic | in_out_cubic | spring`
- holds first/last value outside range

Python: `dot.x = tween(-3, 3, at=0, dur=1.5, ease="out_cubic")`

Optional shorthand strings — `"0.2 * sin(6*t)"` — parse to the same AST. No `eval`.

## Evaluation

`scene.state(t)` → resolves every expression at `t`, returns plain data:

```json
{"t": 2.3, "objects": [{"id": "dot", "type": "circle", "x": 1.2, "y": 0.18, "r": 0.3, "fill": "#ff7f50", "opacity": 1.0}]}
```

Rules:
- Validation happens at authoring time (pydantic). Evaluation bypasses validation for speed.
- Expressions are evaluated per frame, eagerly, in dependency order.
- No mutation of scene objects during evaluation.

## Rendering

- Backend: skia-python. Antialiased vectors, real text shaping.
- `render(path, motion_blur=True, samples=8)` — per frame, rasterize `samples` sub-frames across the shutter interval and average.
- `preview(t, scale=0.25)` — single low-res PNG, fast.
- Output: mp4 via ffmpeg, or PNG sequence.

## Agent Tool Surface

Four calls. All accept/return JSON.

| Tool       | Input                        | Output                                  |
|------------|------------------------------|-----------------------------------------|
| `validate` | scene JSON                   | ok, or structured errors (path, message)|
| `state`    | scene JSON, t                | resolved state at t                     |
| `preview`  | scene JSON, t, scale         | PNG (base64)                            |
| `render`   | scene JSON, path, options    | file path, duration, frame count        |

Errors always name the object id, property, and t where they occurred. Never a bare stack trace.

Exposed as an MCP server and a Claude skill. Schema published from `Scene.model_json_schema()`.

## Non-goals for v1

- Equations / LaTeX
- 3D, camera
- GUI or node editor
- Audio
- Plugin system
- Manim parity of any kind

## Success Criterion

An agent, given a one-sentence prompt and only the four tools, produces a 5-second animation of shapes and a label with eased motion and motion blur that looks better than a manim default. Recorded, under 30 seconds, is the launch demo.

