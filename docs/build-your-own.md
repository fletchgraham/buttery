# Build your own buttery

A hand-typed, minimal reconstruction of buttery's core, in small steps. By the end you will have a
scene that prints "Hello World" and moves a ball back and forth with a sine wave, rendered to an mp4,
and you will understand why buttery is shaped the way it is.

The whole thing is one library file of about 200 lines plus a 10-line scene script. Nothing here is
pasted in whole. Each step adds one idea, you run it, you see what changed.

## The one idea

**The scene is a pure function of time.**

Most animation code keeps state: a ball has a position, each frame you add velocity to it, and frame
100 only makes sense after frames 1 through 99 have run. buttery refuses that. Instead, every property
of every object is an *expression* in terms of time, and asking for frame 100 means calling
`scene.state(t)` with `t = 100 / fps`. Nothing accumulates. Any frame can be computed on its own,
which means frames can be rendered in any order, on any number of cores, and a bug at
second 2.3 can be inspected by evaluating second 2.3.

Everything else follows from that. Three consequences shape the code:

1. **Pydantic models are the schema.** The scene is data, and the same models that give you a nice
   Python API also define the JSON that an AI agent writes. There is no second schema to keep in sync.
2. **Expressions are trees, not code.** `2.5 * sin(2 * t)` is stored as nested nodes
   (`mul`, `sin`, `mul`, a number, a reference to `t`). Python operator overloading builds the tree;
   JSON stores the tree; a tiny evaluator walks the tree. No `eval`, ever.
3. **The renderer is dumb.** It never sees an expression. It gets plain numbers from `state(t)` and
   draws them. That separation is what keeps every other layer testable without pixels.

The layers, top to bottom, in the real library and in ours:

```
Authoring     Python sugar  <->  JSON        (our models, Ref, Op, operator overloading)
Core          Scene, primitives, state(t)    (our Scene.state and resolve)
Renderer      skia: state(t) -> pixels       (our draw_state and render)
```

The real buttery adds an agent tool surface on top (validate, state, preview, render as JSON in,
JSON out, plus an MCP server). We skip that layer. It is a thin wrapper over what you are about to
build.

## What we skip

Keyframe tweens and easing, references between objects, groups, rectangles, lines, stroke, opacity,
color names, motion blur, parallel rendering, structured error reporting, the shorthand string parser,
the CLI. All of those are described at the end so you can see where they would slot in.

## Setup

You need Python 3.11 or newer, `uv`, and `ffmpeg` for the final mp4 (everything before the last
steps works without ffmpeg).

```bash
mkdir mini-buttery && cd mini-buttery
uv init --bare
uv add pydantic skia-python
brew install ffmpeg      # or your platform's equivalent
touch mini_buttery.py hello.py
```

`mini_buttery.py` is the library. `hello.py` is the scene script that uses it. You will run
`uv run python hello.py` many times.

`skia-python` is the same 2D rasterizer that Chrome and Android use, wrapped for Python. It draws
antialiased vector shapes and real text onto a bitmap. It is a big wheel, so the install takes a minute.

A note on pydantic, since you are getting reacquainted: a pydantic model is a class whose attributes
are declared with type annotations. When you construct one, pydantic checks and converts the inputs
to match the annotations, and it can turn the object into a dict or JSON and back. That is the whole
trick, and it is exactly the trick an animation schema needs.

---

## Part 1: The scene is data

### Step 1: A circle is a model

In `mini_buttery.py`:

```python
from typing import Literal

from pydantic import BaseModel, ConfigDict


class Circle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["circle"] = "circle"
    id: str
    x: float = 0.0
    y: float = 0.0
    r: float = 0.5
    fill: str = "#ffffff"
```

What each line does:

- `BaseModel` is pydantic's base class. Subclassing it turns the annotated attributes into validated
  fields.
- `ConfigDict(extra="forbid")` makes pydantic reject any field you did not declare. Without it,
  a typo like `radius=0.4` would be silently ignored, and an agent writing JSON would never learn it
  used the wrong name. Strictness is a feature here.
- `type: Literal["circle"] = "circle"` is a field whose only allowed value is the string `"circle"`.
  It looks pointless now. In Step 4 it becomes the tag that tells circles apart from text in JSON.
- `id: str` has no default, so it is required.
- `x`, `y`, `r` are floats in *world units*, not pixels. We will define world units in Step 8. For
  now: the origin is the center of the frame, and the frame is 8 units wide.

In `hello.py`:

```python
from mini_buttery import Circle

ball = Circle(id="ball", x=1, r=0.4, fill="#ff7f50")
print(ball)
print(repr(ball.x))
```

Run `uv run python hello.py`:

```
type='circle' id='ball' x=1.0 y=0.0 r=0.4 fill='#ff7f50'
1.0
```

Notice `x=1` came out as `1.0`. Pydantic converted the int to the declared float. Now break it on
purpose, temporarily:

```python
Circle(id="ball", radius=0.4)
```

```
pydantic_core._pydantic_core.ValidationError: 1 validation error for Circle
radius
  Extra inputs are not permitted [type=extra_forbidden, input_value=0.4, input_type=float]
```

That error names the field, the problem, and the value. The real buttery reshapes these into JSON
error objects for agents, but the information all comes from pydantic. Delete the broken line.

### Step 2: A model is also JSON

Add to `hello.py`:

```python
print(ball.model_dump())
print(ball.model_dump_json())
```

```
{'type': 'circle', 'id': 'ball', 'x': 1.0, 'y': 0.0, 'r': 0.4, 'fill': '#ff7f50'}
{"type":"circle","id":"ball","x":1.0,"y":0.0,"r":0.4,"fill":"#ff7f50"}
```

`model_dump()` gives a plain dict. `model_dump_json()` gives a JSON string. Going the other way,
`Circle.model_validate(some_dict)` and `Circle.model_validate_json(some_string)` build a model,
running the same validation as the constructor.

This is the "pydantic models are the schema" principle in one line: you wrote one class, and you got
the Python API, the validator, and the file format. An agent can produce that JSON string and it is,
by construction, a valid circle or a precise error.

### Step 3: Text, and a Scene to hold things

Add a second object type below `Circle` in `mini_buttery.py`:

```python
class Text(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["text"] = "text"
    id: str
    content: str = ""
    x: float = 0.0
    y: float = 0.0
    size: float = 0.5
    fill: str = "#ffffff"
```

`size` is the font size in world units, so text scales with everything else. `content` is not
something you would animate, so it is a plain string; keep that distinction in mind for Part 3.

Now the container. Add below `Text`:

```python
class Scene(BaseModel):
    model_config = ConfigDict(extra="forbid")

    size: tuple[int, int] = (1920, 1080)
    fps: int = 60
    duration: float
    background: str = "#111111"
    view_width: float = 8.0
    objects: list[Circle | Text] = []

    def add(self, *objects):
        self.objects.extend(objects)
        return self
```

- `size` is the output in pixels. `view_width` is how many world units span that width. Those two
  numbers are the only link between world units and pixels, and they live on the scene, not on the
  objects.
- `duration` is required; everything else has a default.
- `objects: list[Circle | Text]` says each element is either a Circle or a Text.
- `add` returns `self` so you can chain: `Scene(duration=3).add(ball, greeting)`. (Pydantic copies
  mutable defaults like `[]` per instance, so two scenes do not share one list.)

Update `hello.py` to build a scene:

```python
from mini_buttery import Circle, Scene, Text

ball = Circle(id="ball", x=1, r=0.4, fill="#ff7f50")
greeting = Text(id="greeting", content="Hello World", y=-1.5)

scene = Scene(duration=3, fps=30, size=(960, 540)).add(ball, greeting)
print(scene.model_dump_json(indent=2))
```

Run it. You get the whole scene as indented JSON, with the two objects nested inside `"objects"`.
We use a small size and 30 fps in this tutorial so renders are quick.

### Step 4: Telling circles from text in JSON

Now go the other way. Add to `hello.py`:

```python
scene_json = scene.model_dump_json(indent=2)
loaded = Scene.model_validate_json(scene_json)
print(loaded == scene)
print(type(loaded.objects[1]).__name__)
```

```
True
Text
```

It works, but by trial and error. Given `list[Circle | Text]`, pydantic tries each type in turn and
keeps the one that validates. Here that is fine because each model's `type` literal rejects the
other's data. But when the input is wrong, you get one error from *every* branch of the union
(try `"type": "square"` and you will see a Circle error and a Text error), and pydantic has to
attempt each branch in full before giving up.

The proper tool is a *discriminated union*: tell pydantic which field is the tag. That is what the
`type` field was for. Change the imports and the union in `mini_buttery.py`:

```python
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field
```

Below `Text` and above `Scene`, add:

```python
AnyObject = Annotated[Union[Circle, Text], Field(discriminator="type")]
```

And in `Scene`, change the objects field:

```python
    objects: list[AnyObject] = []
```

`Annotated[X, extra]` is Python's way to attach metadata to a type without changing it. Pydantic
reads the `Field(discriminator="type")` and now looks at `"type"` first, jumps straight to the right
model, and gives a precise error otherwise. Try it in `hello.py`, temporarily:

```python
Scene.model_validate_json('{"duration": 3, "objects": [{"type": "square", "id": "s"}]}')
```

```
objects.0
  Input tag 'square' found using 'type' does not match any of the expected tags: 'circle', 'text'
```

That is a message an agent can act on. Delete the line. The real buttery uses exactly this pattern
with five types (`circle rect line text group`).

### Step 5: Save and load

Two conveniences so the scene script can write a file and something else can read it. Add
`from pathlib import Path` to the top of `mini_buttery.py`, and add two methods to `Scene`:

```python
    def save(self, path):
        Path(path).write_text(self.model_dump_json(indent=2))

    @classmethod
    def load(cls, path):
        return cls.model_validate_json(Path(path).read_text())
```

In `hello.py`, replace the JSON experiments with:

```python
scene.save("hello.json")
print(Scene.load("hello.json") == scene)
```

Run it, then open `hello.json` in an editor. That file is the product. Everything after this point
can be driven by that file alone, with no Python authoring at all. Keep that in mind: the Python
API you are typing is sugar, and the JSON is the contract.

---

## Part 2: From data to pixels

### Step 6: `state(t)`, the seam between data and drawing

Before touching skia, add the most important method in the library. It does almost nothing yet.
In `Scene`:

```python
    def state(self, t: float) -> dict:
        """Every property resolved to a plain value at time t. No expressions survive."""
        return {"t": t, "objects": [obj.model_dump() for obj in self.objects]}
```

In `hello.py`:

```python
print(scene.state(0.0))
```

```
{'t': 0.0, 'objects': [{'type': 'circle', 'id': 'ball', 'x': 1.0, ...}, {'type': 'text', ...}]}
```

Right now nothing depends on `t`, so this is just `model_dump` with a timestamp. But the *contract*
is already set: `state(t)` returns plain dicts of plain numbers and strings. The renderer we write next
will read only from this dict, never from the models. When expressions arrive in Part 3, `state` gets
smarter and the renderer does not change at all.

This is the seam that makes the library agent-friendly. `buttery state scene.json --t 1.25` prints
this dict, so an agent can check where the ball is at 1.25 seconds without rendering a pixel.

### Step 7: A blank frame

Add `import skia` at the top of `mini_buttery.py`, and add at the bottom of the file:

```python
def parse_hex(color: str) -> skia.Color:
    """'#rrggbb' -> skia color."""
    red = int(color[1:3], 16)
    green = int(color[3:5], 16)
    blue = int(color[5:7], 16)
    return skia.Color(red, green, blue)


def render_frame(scene: Scene, t: float, path) -> None:
    width, height = scene.size
    surface = skia.Surface(width, height)
    canvas = surface.getCanvas()
    canvas.clear(parse_hex(scene.background))
    surface.makeImageSnapshot().save(str(path), skia.kPNG)
```

skia vocabulary, the only three words you need:

- A **surface** is a bitmap of a given pixel size, owned by skia.
- A **canvas** is the drawing interface for that surface: clear, draw shapes, transform coordinates.
- A **snapshot** is the surface frozen into an image you can encode as PNG.

`parse_hex` is deliberately tiny: `#rrggbb` only. buttery accepts CSS color names and alpha too, but
that is a table lookup, not an idea.

In `hello.py`:

```python
from mini_buttery import Circle, Scene, Text, render_frame

...

render_frame(scene, 0.0, "frame.png")
```

Run it and open `frame.png`: a 960 by 540 near-black rectangle. That is a rendered frame with
nothing in it, and it proves the pipeline from Python to a PNG on disk.

### Step 8: World units, and the ball appears

Pixel coordinates in skia (and every 2D canvas) start at the top left with y going down. Animation
math wants the origin in the middle with y going up, and it wants to stop caring about the output
resolution. We get all three with one transform on the canvas.

Split the drawing out of `render_frame`. Replace the `render_frame` function with:

```python
def draw_state(scene: Scene, state: dict, canvas: skia.Canvas, px_per_unit: float) -> None:
    width, height = scene.size
    canvas.clear(parse_hex(scene.background))
    canvas.save()
    canvas.translate(width / 2, height / 2)  # origin at the center
    canvas.scale(px_per_unit, -px_per_unit)  # world units, y up
    for obj in state["objects"]:
        paint = skia.Paint(AntiAlias=True, Color=parse_hex(obj["fill"]))
        if obj["type"] == "circle":
            canvas.drawCircle(obj["x"], obj["y"], obj["r"], paint)
    canvas.restore()


def render_frame(scene: Scene, t: float, path) -> None:
    width, height = scene.size
    surface = skia.Surface(width, height)
    draw_state(scene, scene.state(t), surface.getCanvas(), width / scene.view_width)
    surface.makeImageSnapshot().save(str(path), skia.kPNG)
```

- `px_per_unit` is `width / view_width`: at 960 pixels and 8 units wide, one world unit is 120 pixels.
  Change the scene `size` and every object scales with it, because nothing in the objects knows
  about pixels.
- `translate` moves the origin to the center. `scale(px, -px)` converts units to pixels and flips y
  so positive y is up. `save` and `restore` bracket the transform so it does not leak.
- A **paint** in skia is the bundle of "how to draw": color, antialiasing, fill or stroke.
- `draw_state` takes the *state dict*, not the scene's objects. It reads `obj["x"]`, a plain float.
  This is the seam from Step 6 made concrete.

Run `hello.py` again. The ball is at x=1 (a bit right of center), a coral circle with radius 0.4
units, which is 48 pixels. Change `x=1` to `x=-2` in `hello.py` and confirm it moves left. Change
`size=(960, 540)` to `(480, 270)` and confirm the picture is identical, just smaller.

### Step 9: Hello World

Text has one wrinkle: we flipped y so the world is y-up, but glyphs drawn in a flipped coordinate
system come out upside down. The fix is to flip back to pixel space at the text's position, just for
the glyphs.

Add this function above `draw_state`:

```python
def draw_text(obj: dict, canvas: skia.Canvas, px_per_unit: float, paint: skia.Paint) -> None:
    typeface = skia.FontMgr().matchFamilyStyle("Helvetica", skia.FontStyle())
    font = skia.Font(typeface, obj["size"] * px_per_unit)
    text_width = font.measureText(obj["content"])
    cap_height = font.getMetrics().fCapHeight
    canvas.save()
    canvas.translate(obj["x"], obj["y"])
    canvas.scale(1 / px_per_unit, -1 / px_per_unit)  # back to pixels, y down, so glyphs are upright
    canvas.drawString(obj["content"], -text_width / 2, cap_height / 2, font, paint)
    canvas.restore()
```

And in `draw_state`, extend the type check:

```python
        if obj["type"] == "circle":
            canvas.drawCircle(obj["x"], obj["y"], obj["r"], paint)
        elif obj["type"] == "text":
            draw_text(obj, canvas, px_per_unit, paint)
```

Reading `draw_text`:

- A **typeface** is a font family loaded from the system. A **font** is a typeface at a size.
  The size is in pixels, so we multiply the world-unit `size` by `px_per_unit`.
- `measureText` gives the width in pixels so we can center horizontally. `fCapHeight` is the height
  of a capital letter, and shifting the baseline down by half of it centers the text vertically on `y`.
- The `translate` then `scale(1/px, -1/px)` moves to the text's world position and undoes the world
  transform there. Inside that bracket we are in pixel space, y down, exactly what skia's text
  drawing expects.

Run `hello.py`. You have "Hello World" below the ball. If Helvetica is not on your machine, use any
family name you have (`"Arial"`, `"DejaVu Sans"`). buttery walks a list of fallbacks; ours does not.

That is the whole renderer. It is about 40 lines, and it has never heard of time.

---

## Part 3: Time

Now the interesting part. We want to write:

```python
ball.x = 2.5 * sin(2 * T)
```

and have `x` be a *description* of a motion, stored as data, that `state(t)` can evaluate. Three
pieces: a way to refer to `t`, a way to combine things, and a way to evaluate.

### Step 10: A reference to time

Add to `mini_buttery.py`, above `Circle`:

```python
class Ref(BaseModel):
    """A reference to something that is only known at evaluation time. For now: only 't'."""

    model_config = ConfigDict(extra="forbid")

    ref: Literal["t"]


T = Ref(ref="t")
```

That is it. `T` is a value that means "scene time, whatever it is when you ask". In JSON it is
`{"ref": "t"}`. The real buttery serializes it as the bare string `"t"`, and also allows
`"ball.x"` to reference another object's property. That takes a custom pydantic hook, so we use a
small model and keep the idea.

### Step 11: Operators are nodes

An operator node is a name plus a list of arguments, and each argument is itself a number, a
reference, or another node. Add below `Ref`:

```python
class Op(BaseModel):
    """An operator applied to some arguments, which are themselves expressions."""

    model_config = ConfigDict(extra="forbid")

    op: Literal["add", "sub", "mul", "div", "neg", "sin", "cos"]
    args: list["Expr"]


Expr = Union[float, Ref, Op]

Op.model_rebuild()
```

Two pydantic details:

- `Expr` is a *union* of the three things a property can be. The union is not discriminated because
  a float has no tag. Pydantic tries float, then Ref, then Op, and since Ref and Op have different
  required fields there is no ambiguity.
- `Op` mentions `Expr` before it exists, so the annotation is a string, `"Expr"`. This is called a
  forward reference. After `Expr` is defined we call `Op.model_rebuild()` so pydantic can go back and
  resolve the string into the real type. Any time a model refers to itself or to something defined
  later, you will do this dance.

`2 * sin(t)` is now data:

```python
Op(op="mul", args=[2.0, Op(op="sin", args=[Ref(ref="t")])])
```

Nobody wants to type that, which is Step 12. But note what we have: a *tree*. The leaves are numbers
and references. The inner nodes are ops. This is the expression tree the whole library is built on.
The opcode list is tiny on purpose. buttery adds `abs min max clamp smoothstep noise` and a `tween`
node; the shape is the same.

Now let the objects accept expressions. In `Circle` and `Text`, change every animatable float:

```python
    x: Expr = 0.0
    y: Expr = 0.0
    r: Expr = 0.5      # Circle
    size: Expr = 0.5   # Text
```

Leave `id`, `content`, and `fill` alone. A plain float still validates as an `Expr`, so `hello.py`
runs exactly as before. Constants are the trivial case of an expression.

(`fill` could be animatable too. buttery tweens colors between keyframes, but a color is not a number
you can multiply, so it lives in a separate `ColorExpr` union. We keep colors static.)

### Step 12: Python operators build the tree

Add above `Ref`:

```python
class Arithmetic:
    """Mixin: Python operators build Op nodes instead of computing numbers."""

    def __add__(self, other):
        return Op(op="add", args=[self, other])

    def __radd__(self, other):
        return Op(op="add", args=[other, self])

    def __sub__(self, other):
        return Op(op="sub", args=[self, other])

    def __rsub__(self, other):
        return Op(op="sub", args=[other, self])

    def __mul__(self, other):
        return Op(op="mul", args=[self, other])

    def __rmul__(self, other):
        return Op(op="mul", args=[other, self])

    def __truediv__(self, other):
        return Op(op="div", args=[self, other])

    def __rtruediv__(self, other):
        return Op(op="div", args=[other, self])

    def __neg__(self):
        return Op(op="neg", args=[self])
```

Then make `Ref` and `Op` inherit from it, mixin first:

```python
class Ref(Arithmetic, BaseModel):
    ...

class Op(Arithmetic, BaseModel):
    ...
```

And add two helper functions below `T = Ref(ref="t")`:

```python
def sin(x):
    return Op(op="sin", args=[x])


def cos(x):
    return Op(op="cos", args=[x])
```

How `2 * T` works: Python asks `int.__mul__(2, T)`, which returns `NotImplemented` because ints do
not know about Refs. Python then tries the reflected version, `T.__rmul__(2)`, and that builds
`Op(op="mul", args=[2, T])`. Pydantic validates the args, converting `2` to `2.0`. The result is
an `Op`, which also has these methods, so `2 * T + 1` keeps building outward.

The point: Python's own syntax is our authoring language, and it produces the same tree an agent
would write as JSON. There is no parser and no `eval`. `sin` is a plain function because Python has
no operator for it. (buttery also accepts shorthand strings like `"0.2 * sin(6*t)"` and parses
them with a small hand-written parser into the same tree, again with no `eval`.)

In `hello.py`:

```python
from mini_buttery import Circle, Scene, T, Text, render_frame, sin

...
ball.x = 2.5 * sin(2 * T)
print(ball.x)
print(ball.model_dump())
```

```
op='mul' args=[2.5, Op(op='sin', args=[Op(op='mul', args=[2.0, Ref(ref='t')])])]
{'type': 'circle', 'id': 'ball', 'x': {'op': 'mul', 'args': [2.5, {'op': 'sin', 'args': [{'op': 'mul', 'args': [2.0, {'ref': 't'}]}]}]}, 'y': 0.0, 'r': 0.4, 'fill': '#ff7f50'}
```

The expression is stored on the object and dumps as nested dicts. (One pydantic note: assigning
`ball.x = ...` after construction is *not* validated by default. buttery sets
`validate_assignment=True` in its models so a typo on assignment fails immediately. Try adding it
to `Circle`'s config if you like.)

Do not run `render_frame` yet. `state` still does `model_dump`, which would hand the renderer a
dict where `x` is a tree, and `drawCircle` would choke on it. That is the next step.

### Step 13: Evaluating the tree

Add below the `cos` helper:

```python
import math   # move this to the top of the file with the other imports

OPS = {
    "add": lambda a, b: a + b,
    "sub": lambda a, b: a - b,
    "mul": lambda a, b: a * b,
    "div": lambda a, b: a / b,
    "neg": lambda a: -a,
    "sin": math.sin,
    "cos": math.cos,
}


def resolve(value, t: float):
    """Turn a property value into a plain value at time t."""
    if isinstance(value, Ref):
        return t
    if isinstance(value, Op):
        resolved_args = [resolve(arg, t) for arg in value.args]
        return OPS[value.op](*resolved_args)
    return value  # a number or a string: already plain
```

`resolve` is the entire evaluator. It walks the tree: a reference becomes `t`, an op resolves its
arguments first and then applies the function, and anything else (a float, or a string like
`content` or `fill`) passes through untouched. That last line is why we did not need a separate
code path for static properties.

Now update `Scene.state` to use it:

```python
    def state(self, t: float) -> dict:
        """Every property resolved to a plain value at time t. No expressions survive."""
        resolved_objects = []
        for obj in self.objects:
            resolved_objects.append({name: resolve(value, t) for name, value in obj})
        return {"t": t, "objects": resolved_objects}
```

Iterating a pydantic model yields `(field_name, value)` pairs, so this builds a dict per object with
every field resolved. The renderer from Part 2 will not notice anything changed.

Check it in `hello.py`:

```python
print(scene.state(0.0)["objects"][0]["x"])
print(scene.state(0.785)["objects"][0]["x"])
```

```
0.0
2.4999...
```

At t=0 the sine is 0; at t=π/4 the argument is π/2 and the ball is at its rightmost. `state(t)` is
now a real function of time, and it is pure: it reads the scene, never writes it, and calling it
twice with the same `t` gives the same answer.

buttery does the same thing with one optimization: it compiles each tree into a closure once, so
per-frame evaluation does not re-walk the tree and re-look-up opcodes. It also orders properties so
that ones referencing other objects are computed after their targets. Both are speed and features,
not a different idea.

### Step 14: The ball moves

Decide the motion. We want one full back-and-forth over the 3 second scene, so the sine's argument
should go from 0 to 2π as `t` goes from 0 to 3. Update `hello.py` to its near-final form:

```python
import math

from mini_buttery import Circle, Scene, T, Text, render_frame, sin

ball = Circle(id="ball", r=0.4, fill="#ff7f50")
ball.x = 2.5 * sin((2 * math.pi / 3) * T)
greeting = Text(id="greeting", content="Hello World", y=-1.5, size=0.5)

scene = Scene(duration=3, fps=30, size=(960, 540)).add(ball, greeting)

if __name__ == "__main__":
    for t in (0.0, 0.75, 1.5, 2.25):
        render_frame(scene, t, f"frame_{t}.png")
```

`(2 * math.pi / 3)` is computed by Python into a single float before it ever meets `T`, so the tree
stays small: `mul(2.5, sin(mul(2.094, t)))`. Run it and open the four PNGs. The ball is centered at
0, far right at 0.75, centered at 1.5, far left at 2.25. You rendered four frames, in any order you
liked, with no state between them.

### Step 15: Render the movie

A movie is that loop over every frame, plus ffmpeg. Add `import subprocess` at the top and this at
the bottom of `mini_buttery.py`:

```python
def render(scene: Scene, path) -> None:
    frames_dir = Path("frames")
    frames_dir.mkdir(exist_ok=True)
    for frame_index in range(scene.frame_count):
        t = frame_index / scene.fps
        render_frame(scene, t, frames_dir / f"frame_{frame_index:05d}.png")
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(scene.fps),
         "-i", str(frames_dir / "frame_%05d.png"), "-pix_fmt", "yuv420p", str(path)],
        check=True,
    )
```

And a property on `Scene`:

```python
    @property
    def frame_count(self) -> int:
        return round(self.duration * self.fps)
```

`t = frame_index / fps` is the only place time is ever generated. Everything else consumes it.

In `hello.py`, replace the four-frame loop:

```python
if __name__ == "__main__":
    from mini_buttery import render
    render(scene, "hello.mp4")
```

Run it. Ninety PNGs land in `frames/`, ffmpeg stitches them, and `hello.mp4` plays a coral ball
swinging left and right over "Hello World". That is the deliverable.

Because each `render_frame` call is independent, this loop is trivially parallel. buttery hands
chunks of frame indices to a process pool, one rasterizer per process, and gets all your cores for
free. It also renders eight sub-frames spread across half a frame interval and averages them, which
is motion blur: again just more calls to `state(t)` at slightly different `t`.

### Step 16: The JSON is the whole animation

Last step, and it closes the loop. Add to the `__main__` block of `hello.py` before the render:

```python
    scene.save("hello.json")
```

Run it, then open `hello.json` and find the ball's `x`:

```json
"x": {
  "op": "mul",
  "args": [
    2.5,
    {"op": "sin", "args": [{"op": "mul", "args": [2.0943951023931953, {"ref": "t"}]}]}
  ]
}
```

The motion you wrote as `2.5 * sin(...)` is sitting in a text file as a tree. Now prove that the
file is sufficient. Make a new script, `from_json.py`:

```python
from mini_buttery import Scene, render

scene = Scene.load("hello.json")
print(scene.state(0.75)["objects"][0]["x"])
render(scene, "from_json.mp4")
```

Same movie, and the Python authoring layer was never imported. An agent that can write that JSON,
or hand-edit the `2.5` to a `3.5`, can make animations with this library. That is what
"agent-friendly" means in practice: the schema is small, explicit, and validated, and the whole
scene is inspectable at any `t`.

---

## What you built, and how it maps to buttery

| Your `mini_buttery.py` | buttery module | What buttery adds |
|---|---|---|
| `Ref`, `Op`, `Expr`, `Arithmetic`, `T`, `sin` | `expr.py` | `Tween` nodes with easing, references to other objects (`ball.ref.x`), more ops, `ColorExpr`, bare-string refs in JSON |
| (none) | `parse.py` | shorthand strings like `"0.2 * sin(6*t)"` parsed into the same tree, no `eval` |
| `Circle`, `Text`, `AnyObject` | `objects.py` | `Rect`, `Line`, `Group` (nested children with transforms), stroke, opacity, a `Kind` marker so the library knows which fields are animatable numbers versus colors |
| `Scene`, `state`, `save`, `load` | `scene.py` | semantic validation: unique ids, references resolve, no dependency cycles; structured error objects |
| `OPS`, `resolve` | `evaluate.py`, `ops.py` | compile each tree to a closure once; evaluate properties in dependency order so cross-object references work |
| `parse_hex`, `draw_state`, `draw_text`, `render_frame`, `render` | `render.py`, `color.py` | CSS color names, text wrapping, motion blur via averaged sub-frames, parallel frame rendering, `preview()` at reduced scale |
| (none) | `tools.py`, `cli.py`, `mcp_server.py` | `validate / state / preview / render` as JSON-in JSON-out functions, a CLI, and an MCP server so an agent can call them |

Every addition in the right column is a feature on top of a piece you have already typed. None of
them change the shape.

The philosophy, restated now that you have the code in your hands:

- **`state(t)` is pure.** Your `resolve` reads and never writes. That is why Step 14 could render
  frames in any order, why Step 15 is parallelizable, and why a bug at second 2.3 is reproducible by
  calling `state(2.3)`.
- **One schema.** You wrote `Circle` once and got a constructor, a validator, a dict, and a file
  format. buttery's JSON schema for agents is literally `Scene.model_json_schema()`.
- **Expressions are data.** A motion is a tree that can be stored, diffed, validated, and handed
  between a human and an agent. Python operators are a convenience for building it.
- **The renderer is dumb on purpose.** It reads plain numbers from a dict. Every other layer can be
  tested with `assert scene.state(1.0)["objects"][0]["x"] == ...`, no pixels involved.

## If you want to keep going

Each of these is a small step from where you are, in roughly increasing size:

1. **`validate_assignment=True`** on the models, so `ball.x = "oops"` fails at the assignment.
2. **A `tween` node.** A model with `keys: list[tuple[float, float]]` and an `ease` name, and a
   branch in `resolve` that finds the two surrounding keys and interpolates. This is the workhorse of
   real explainer animations, where most motion is "go from here to there over this long."
3. **References to other objects.** Widen `Ref` to allow `"ball.x"`, make `state` evaluate
   properties in dependency order, and reject cycles. Then a ring can say `ring.x = ball.ref.x` and
   follow the ball for free. This is the step that turns a toy into buttery.
4. **Motion blur.** In `render_frame`, call `draw_state` several times at `t` plus small offsets
   and average the resulting arrays.
