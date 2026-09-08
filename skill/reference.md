# Recipes and taste notes

## Recipes (values are numeric properties unless noted)

**Fade in at 0.5s over 0.4s**: `"opacity": {"op": "tween", "keys": [[0.5, 0], [0.9, 1]], "ease": "out_quad"}`

**Enter from the left, settle with overshoot**: `"x": {"op": "tween", "keys": [[0.2, -5], [1.0, -1.5]], "ease": "spring"}`

**Stagger**: same tween on several objects, keys shifted by 0.15s each.

**Bounce (continuous)**: `"y": "-0.5 + 0.9 * abs(sin(4*t))"`

**Orbit**: put children on a `group` and set `"rotation": "90*t"` on the group.

**Follow another object**: `"x": "ball.x"`, or lag it: `"x": "ball.x - 0.3"`.

**Realistic bounce (decaying ballistic arcs)**: sum parabola windows; each is zero outside its window so no mod/floor is needed. Arc k: `4*h*u*(1-u)` with `u = clamp((t - start)/dur, 0, 1)`; next arc has `h *= e*e`, `dur *= e`, `start += dur` (e ~ 0.65 restitution). Release is `h0*(1 - v*v)`, `v = clamp((t - t0)/fall, 0, 1)`. See `examples/squash_bounce.py`.

**Squash on impact**: draw the ball as a rect with `corner_radius = r` (a circle), then `w = 2r*(1+s)`, `h = 2r*(1-s)` with `s = a * (1 - smoothstep(0, 0.07, abs(t - impact)))` summed over impacts; set `y = floor + h/2 + height` so the bottom edge stays on the floor.

**Squash on landing** (rect): `"h": "0.8 - 0.3 * smoothstep(0.9, 1.0, abs(cos(4*t)))"`

**Pulse**: `"r": "0.3 + 0.05 * sin(tau * t)"`

**Wobble/noise**: `"rotation": "8 * noise(2*t)"`; use a second arg to decorrelate: `noise(2*t, 3)`.

**Color change**: `"fill": {"op": "tween", "keys": [[1, "#4a90d9"], [1.5, "coral"]], "ease": "in_out_quad"}`

**Multi-stage path**: one tween with several keys: `"keys": [[0, -3], [1, 0], [2, 0], [3, 3]]` (the flat segment holds).

**Hold then go**: keys `[[0, 0], [1.2, 0], [2, 3]]`.

## Taste

- Ease almost everything. `out_cubic` for arrivals, `in_out_cubic` for point-to-point, `spring` sparingly for emphasis.
- Leave air: start motion at 0.3 to 0.5 s, finish 0.5 s before the end.
- Motion blur is on by default (180 degree shutter, 8 samples). Fast crosses of the frame in under 0.5 s read well because of it.
- Stroke widths around 0.03 to 0.06 units; text size 0.35 to 0.5 for labels, up to 0.8 for titles.
- Dark background (`#0e0e11`, `#111111`) with one warm accent (`coral`, `#ff7f50`) and one cool (`#4a90d9`) is a safe palette.
- Keep ids short and meaningful (`ball`, `shadow`, `title`); errors quote them.

## Python sugar (same models)

```python
from buttery import *
dot = Circle("dot", r=0.3, fill="coral")
dot.x = tween(-3, 3, at=0, dur=1.5, ease="out_cubic")
dot.y = 0.2 * sin(6 * T)
ring = Circle("ring", fill=None, stroke="white", x=dot.ref.x, r=dot.ref.r + 0.5)
scene = Scene(duration=3).add(dot, ring)
scene.save("scene.json"); scene.render("out.mp4")
```

Read `obj.prop` to get the stored expression; use `obj.ref.prop` to reference it from another object.

## Code

A `code` object is a monospace block anchored at its top-left `(x, y)`; `size` is the font size. Characters sit
on a fixed grid, column `c` of row `r` at `(x + c*char_width*size, y - r*line_height*size)` (defaults 0.6 and
1.4), so layout never depends on the font. Use spaces, not tabs. In Python, `code.width` and `code.height` are
known without rendering: `code.x = -code.width / 2` centers the block.

Parts of the snippet are selected with `spans`, each with an `id` and animatable `fill`, `background`, `opacity`:

```json
{"id": "fn", "type": "code", "size": 0.34, "content": "def f(x):\n    return x + 1",
 "spans": [
   {"id": "kw",   "token": "return", "fill": "coral"},
   {"id": "arg",  "token": "x", "nth": -1, "background": "#2b2b3d"},
   {"id": "l1",   "line": 1, "opacity": {"op": "tween", "keys": [[0.5, 0], [1, 1]]}},
   {"id": "call", "line": 2, "chars": [11, 16], "fill": "#e0a54a"}
 ]}
```

- `line: n` (1-based) selects a whole line. `token: "x"` selects the nth Python token with exactly that text
  (`nth` from 0, negative from the end); add `line` to search only that line. `chars: [a, b]` is a half-open
  range of offsets into the snippet, or of columns when `line` is given. Only `token` needs valid Python.
- `buttery state` shows each span's resolved `start`/`end`, so you can check what a selector picked.
- Span `opacity` multiplies the block's (like a group), `fill` replaces it, `background` paints the cells.
  Later spans win where fills overlap.
- **Reveal line by line**: one span per line with `opacity` tweening 0 -> 1 on its beat.
- **Highlight, then let go**: tween `background` from `"transparent"` to a color and back; tween `fill` from
  the block's color to an accent and back. The first key holds before its time, so the span is invisible until then.
- Python: `code.select("kw", token="return", fill="coral")` builds and appends the span, and fails at once if
  the selector does not resolve. See `examples/code_walk.py`.

## Algorithm walkthroughs (staged, data-driven scenes)

Simulate the algorithm in plain Python first and record a list of steps (what moves, from where, to where,
at which beat). Then turn each step into keyframes: a cell is a `group` (rect + text) whose `x`/`y` tween
from its slot to its destination at that beat, and holds there forever after because a tween holds its
last key. Highlights are multi-key tweens on `scale` and `stroke` (base -> white -> base); per-step captions
are separate `text` objects with an opacity window. Draw order matters when cells cross each other: add the
cells that move on top last. Arc a move with `y = tween(...) + lift * 4*u*(1-u)`, `u = clamp((t - t0)/dur, 0, 1)`.
See `examples/merge_sorted.py`.
