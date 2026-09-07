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
