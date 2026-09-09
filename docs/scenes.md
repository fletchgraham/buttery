# Scenes

A scene is JSON. The Python API builds the same models, so everything on this page applies to both. `buttery
schema` prints the full JSON schema, generated from the pydantic models with `Scene.model_json_schema()`.

```json
{
  "duration": 5, "fps": 60, "size": [1920, 1080], "background": "#111111", "view_width": 8,
  "objects": [
    {"id": "dot", "type": "circle", "r": 0.3, "fill": "coral",
     "x": {"op": "tween", "keys": [[0, -3], [1.5, 3]], "ease": "out_cubic"},
     "y": "0.2 * sin(6*t)"},
    {"id": "ring", "type": "circle", "fill": null, "stroke": "white", "x": "dot.x", "r": "dot.r + 0.5"},
    {"id": "label", "type": "text", "content": "Hello", "y": -1.6, "size": 0.4, "fill": "#dddddd"}
  ]
}
```

Only `duration` is required. The defaults are 60 fps, 1920×1080, a near-black background, and a view 8 units
wide.

## Coordinates

World units, origin at the center, **y up**. The frame is `view_width` units wide, so with the default of 8,
x runs from -4 to 4 and at 16:9 y runs from -2.25 to 2.25. `size` and `view_width` are the only link between
world units and pixels, and they live on the scene, not on the objects. Angles are degrees, counter-clockwise.
Colors are hex (`#ff7f50`) or CSS names (`coral`).

## Primitives

Every object needs a unique `id` (global, including inside groups) and accepts `opacity`. Properties marked
*static* are plain values; every other property is animatable and accepts an [expression](#expressions).

| type   | properties |
|--------|-----------|
| circle | `x y r fill stroke stroke_width` |
| rect   | `x y w h corner_radius rotation fill stroke stroke_width` (`x`, `y` is the center) |
| line   | `x1 y1 x2 y2 stroke stroke_width` |
| text   | `x y size fill` · static: `content font align max_width line_height`. Newlines in `content` start new lines; `max_width` wraps at words. |
| code   | `x y size fill` · static: `content font char_width line_height theme spans`. A monospace block with its top-left at (`x`, `y`) on a fixed grid. |
| span   | only inside `code.spans`: `fill background opacity` · static selectors: `line token nth chars` |
| group  | `x y rotation scale children`. Children are transformed with the group; their ids are still global. |

`fill` and `stroke` accept a color, `null` (not drawn), or a tween between colors.

## Expressions

Any numeric property accepts:

| form | example |
|------|---------|
| a number | `1.5` |
| time | `"t"` |
| a reference to another object's property | `"dot.x"` |
| a shorthand string | `"0.2 * sin(6*t)"`, `"dot.r + 0.5"` |
| an op node | `{"op": "mul", "args": [0.2, {"op": "sin", "args": [{"op": "mul", "args": [6, "t"]}]}]}` |
| a tween | `{"op": "tween", "keys": [[0, -3], [1.5, 3]], "ease": "out_cubic"}` |

Shorthand strings are parsed into the same op tree, never `eval`ed. The parser knows `pi` and `tau`.

**Ops**: `add sub mul div neg sin cos abs min max clamp smoothstep noise`.

- `clamp(x, lo, hi)` and `smoothstep(edge0, edge1, x)` follow the GLSL conventions.
- `noise(x)` is smooth 1D noise in roughly -1..1; a second argument, `noise(x, 3)`, picks a different
  channel so two objects do not wobble in sync.

**Tween**: `{"op": "tween", "keys": [[t, v], ...], "ease": "..."}`. Keys are sorted by time. The value holds
at the first key before it and at the last key after it, so a tween is also a way to say "hold, then go".
Color properties tween between colors: `"keys": [[1, "#4a90d9"], [1.5, "coral"]]`.

**Eases**: `linear in_quad out_quad in_out_quad out_cubic in_out_cubic spring`.

References form a dependency graph across objects. A ring can follow a dot with `"x": "dot.x"`, and an edge
can join two nodes with `"x1": "a.x", "y1": "a.y", "x2": "b.x", "y2": "b.y"`. Only numeric properties can be
referenced, and cycles are rejected at validation.

## Code

A `code` object is a monospace block anchored at its top-left (`x`, `y`); `size` is the font size. Characters
sit on a fixed grid, column `c` of row `r` at `(x + c*char_width*size, y - r*line_height*size)` (defaults 0.6
and 1.4), so layout never depends on the font. Use spaces, not tabs. `theme: "default"` syntax-highlights
Python; a mapping from token kind to color (`keyword`, `name`, `builtin`, `string`, `number`, `comment`) is a
custom theme.

Parts of the snippet are selected with `spans`, each with an `id` and animatable `fill`, `background`, and
`opacity`:

```json
{"id": "fn", "type": "code", "size": 0.34, "theme": "default", "content": "def f(x):\n    return x + 1",
 "spans": [
   {"id": "kw",   "token": "return", "fill": "coral"},
   {"id": "arg",  "token": "x", "nth": -1, "background": "#2b2b3d"},
   {"id": "l1",   "line": 1, "opacity": {"op": "tween", "keys": [[0.5, 0], [1, 1]]}},
   {"id": "call", "line": 2, "chars": [11, 16], "fill": "#e0a54a"}
 ]}
```

- `line: n` (1-based) selects a whole line.
- `token: "x"` selects the nth Python token with exactly that text (`nth` from 0, negative from the end).
  Add `line` to search only that line. Only `token` needs the content to be valid Python.
- `chars: [a, b]` is a half-open range of offsets into the snippet, or of columns when `line` is given.
- Span `opacity` multiplies the block's, `fill` replaces it, and `background` paints the cells. Later spans win
  where fills overlap.
- `buttery state` shows each span's resolved `start` and `end`, so you can check what a selector picked.

## Validation

Two layers, both run by `buttery validate` and by loading a scene in Python:

- **Structural**, from pydantic: unknown fields are rejected, op arity is checked, colors must parse, ids must
  be well formed.
- **Semantic**: ids are unique across the whole scene, references resolve to numeric animatable properties,
  there are no dependency cycles, and tween keys match the property kind (numbers for numeric properties,
  colors for `fill` and `stroke`).

Errors are objects, not stack traces:

```json
{"ok": false, "errors": [
  {"path": "objects[1].x", "message": "reference 'dott.x': no object with id 'dott'",
   "object": "ring", "property": "x", "t": null}
]}
```

## Evaluation and rendering

- Each expression is compiled to a closure once. `state(t)` walks the objects in dependency order and never
  mutates the scene, so every frame is independent.
- Motion blur samples `samples` sub-frames spread across `shutter` × the frame interval and averages them.
  The default, 8 samples at 0.5, is a 180° shutter.
- Frames render in parallel on every core and stream to ffmpeg for `.mp4` and `.mov`, or to a directory as
  numbered PNGs.

## Recipes

Values are numeric properties unless noted.

- **Fade in at 0.5 s over 0.4 s**: `"opacity": {"op": "tween", "keys": [[0.5, 0], [0.9, 1]], "ease": "out_quad"}`
- **Enter from the left, settle with overshoot**: `"x": {"op": "tween", "keys": [[0.2, -5], [1.0, -1.5]], "ease": "spring"}`
- **Stagger**: the same tween on several objects, keys shifted by 0.15 s each.
- **Hold then go**: `"keys": [[0, 0], [1.2, 0], [2, 3]]`.
- **Multi-stage path**: `"keys": [[0, -3], [1, 0], [2, 0], [3, 3]]` (the flat segment holds).
- **Bounce (continuous)**: `"y": "-0.5 + 0.9 * abs(sin(4*t))"`
- **Squash on landing** (rect): `"h": "0.8 - 0.3 * smoothstep(0.9, 1.0, abs(cos(4*t)))"`
- **Pulse**: `"r": "0.3 + 0.05 * sin(tau * t)"`
- **Wobble**: `"rotation": "8 * noise(2*t)"`; decorrelate a second object with `noise(2*t, 3)`.
- **Orbit**: put children on a `group` and set `"rotation": "90*t"` on the group.
- **Follow**: `"x": "ball.x"`, or lag it: `"x": "ball.x - 0.3"`.
- **Color change**: `"fill": {"op": "tween", "keys": [[1, "#4a90d9"], [1.5, "coral"]], "ease": "in_out_quad"}`
- **Realistic bounce**: sum parabola windows that are zero outside their interval, each arc
  `4*h*u*(1-u)` with `u = clamp((t - start)/dur, 0, 1)`, and decay `h` and `dur` per bounce. See
  [`examples/squash_bounce.py`](https://github.com/fletchgraham/buttery/blob/main/examples/squash_bounce.py).

## Taste

- Ease almost everything. `out_cubic` for arrivals, `in_out_cubic` for point-to-point, `spring` sparingly.
- Leave air: start motion at 0.3 to 0.5 s, finish 0.5 s before the end.
- Motion blur is on by default. Fast crosses of the frame in under 0.5 s read well because of it.
- Stroke widths around 0.03 to 0.06 units; text size 0.35 to 0.5 for labels, up to 0.8 for titles.
- A dark background (`#0e0e11`, `#111111`) with one warm accent (`coral`) and one cool (`#4a90d9`) is a safe
  palette.
- Keep ids short and meaningful (`ball`, `shadow`, `title`); errors quote them.
