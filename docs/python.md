# Python

The Python API is sugar over the same pydantic models that define the [JSON format](scenes.md). Anything you
build here can be saved as JSON and vice versa.

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

## Objects

The first positional argument is the `id`. Every other property is a keyword, and every animatable property
can also be assigned after construction.

```python
Circle("dot", x=0, y=0, r=0.5, fill="white", stroke=None, stroke_width=0.05, opacity=1)
Rect("box", x=0, y=0, w=1, h=1, corner_radius=0, rotation=0, fill="white")
Line("edge", x1=-1, y1=0, x2=1, y2=0, stroke="white", stroke_width=0.05)
Text("label", content="Hello", x=0, y=0, size=0.5, fill="white", align="center", max_width=None)
Code("fn", content="def f(x):\n    return x + 1", size=0.34, theme="default", spans=[...])
Group("tree", x=0, y=0, rotation=0, scale=1, children=[...])
```

The [Scenes](scenes.md#primitives) page lists every property of every type. Ids are global, including inside
groups, and errors quote them.

## Expressions

Any numeric property accepts a number or an expression in terms of time. `T` is scene time in seconds.
Python operators on `T`, on references, and on other expressions build a tree; nothing is evaluated until
`state(t)`.

```python
dot.y = 0.2 * sin(6 * T)
dot.r = 0.3 + 0.05 * sin(tau * T)
box.rotation = 8 * noise(2 * T)
ball.y = -0.5 + 0.9 * abs(sin(4 * T))
```

Available functions: `sin cos abs min_ max_ clamp smoothstep noise`. `min_` and `max_` have trailing
underscores so they do not shadow the builtins; the JSON ops are `min` and `max`.

## Tweens and keyframes

`tween` goes from one value to another starting at `at` over `dur` seconds. `keyframes` takes several keys.
Both hold the first value before their first key and the last value after their last key.

```python
dot.x = tween(-3, 3, at=0.5, dur=1.5, ease="out_cubic")
dot.x = keyframes([(0, -3), (1, 0), (2, 0), (3, 3)], ease="in_out_cubic")
dot.x = keyframes({0: -3, 1: 0, 2: 0, 3: 3})
```

Eases: `linear in_quad out_quad in_out_quad out_cubic in_out_cubic spring`.

Colors tween too. `fill` and `stroke` accept a color, `None`, or a tween between colors:

```python
dot.fill = tween("#4a90d9", "coral", at=1, dur=0.5, ease="in_out_quad")
```

## References

`obj.prop` reads the stored expression. `obj.ref.prop` makes a *reference* to it that another object can
use. The spec's `dot.r + 0.5` became `dot.ref.r + 0.5` because a plain attribute read cannot be both a
value and a reference.

```python
ring.x = dot.ref.x
ring.r = dot.ref.r + 0.5
shadow.x = ball.ref.x - 0.3
```

References form a dependency graph. Validation rejects cycles and references to properties that do not
exist or are not numeric.

## Scene

```python
scene = Scene(duration=5, fps=60, size=(1920, 1080), background="#111111", view_width=8)
scene.add(a, b, c)          # returns the scene, so it chains
scene.check()               # list of SceneError, empty when the scene is valid
scene.state(t)              # {"t": t, "objects": [...]} with every property resolved
scene.preview(t, scale=0.25, path="p.png")
scene.render("out.mp4", motion_blur=True, samples=8, shutter=0.5, workers=None)
scene.render("frames/")     # PNG sequence, no ffmpeg needed
scene.save("scene.json")
Scene.load("scene.json")
scene.find("dot")           # look an object up by id, including inside groups
```

Coordinates are world units with the origin at the center and y up. The frame is `view_width` units wide,
so by default x runs from -4 to 4 and at 16:9 y runs from -2.25 to 2.25.

## Code blocks

A `Code` object lays its characters on a fixed grid, so `code.width` and `code.height` are known without
rendering:

```python
code = Code("fn", content=SRC, size=0.34, theme="default")
code.x = -code.width / 2
code.y = code.height / 2
```

Spans select part of the snippet and give it their own animatable `fill`, `background`, and `opacity`:

```python
Span("kw", token="return", fill="coral")
Span("arg", token="x", nth=-1, background="#2b2b3d")
Span("l1", line=1, opacity=tween(0, 1, at=0.5, dur=0.5))
Span("call", line=2, chars=(11, 16), fill="#e0a54a")
```

See [Scenes](scenes.md#code) for the selector rules.

## Errors

Structural problems (unknown fields, wrong arity, bad colors) raise pydantic's `ValidationError` at construction.
Semantic problems (duplicate ids, unresolved references, cycles, tween key kinds) are found by `scene.check()`,
which returns a list of `SceneError` objects with the same `path`, `message`, `object`, `property`, and `t`
fields the CLI prints. Loading a scene from JSON runs both kinds of check. `EvalError` and `RenderError`
cover evaluation and rasterization.
