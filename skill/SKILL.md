---
name: buttery
description: Author and render 2D explainer animations as JSON scenes where every property is a pure function of time. Use when asked to make an explainer animation, animate shapes and labels, produce an mp4 of eased motion, or work with buttery scene JSON. Provides validate / state / preview / render.
allowed-tools: Bash(buttery:*), Bash(uv run:*), Bash(uvx buttery:*), Bash(python3:*), Bash(python:*), Bash(ls:*), Bash(cat:*), Bash(for:*), Read, Write, Edit
---

# buttery

A scene is JSON. `state(t)` resolves every property at time `t`; nothing accumulates between frames.
You author the JSON, validate it, look at a few previews, then render.

Run commands from your working directory, where `scene.json` lives. Do not `cd` anywhere.

```bash
buttery validate scene.json                 # ok, or structured errors
buttery state scene.json --t 1.25           # resolved values at t
buttery preview scene.json --t 1.25 --out preview.png --scale 0.25
buttery render scene.json out.mp4           # motion blur on; or a directory for PNGs
buttery schema                              # full JSON schema
```

If `buttery` is not on your PATH, use `uvx buttery ...` (no install needed), or when this skill sits inside
a checkout of the repo, `uv run --project ${CLAUDE_SKILL_DIR}/.. buttery ...`. Both keep your working directory.
Scripting the JSON with `python3` is fine; the CLI is the source of truth for validation.

Errors name the `path`, `object` id, `property`, and `t` where relevant. Fix and re-validate.

## Workflow

1. Sketch the beats: what moves when, in seconds. Default duration 5s, 60 fps, 1920x1080.
2. Write `scene.json` (format below). Prefer `tween` for staged motion, expressions for continuous motion.
3. `validate`, then `preview` at 2 to 3 key times and Read the PNGs to check composition.
4. `render` to an `.mp4`. Report the path.

## Scene format

Coordinates: world units, origin at center, **y up**. The frame is `view_width` (default 8) units wide,
so x runs -4..4 and at 16:9 y runs -2.25..2.25. Colors: hex or CSS names. Angles in degrees, counter-clockwise.

```json
{
  "duration": 5, "fps": 60, "size": [1920, 1080], "background": "#111111",
  "objects": [
    {"id": "dot", "type": "circle", "r": 0.3, "fill": "coral",
     "x": {"op": "tween", "keys": [[0, -3], [1.5, 3]], "ease": "out_cubic"},
     "y": "0.2 * sin(6*t)"},
    {"id": "ring", "type": "circle", "fill": null, "stroke": "white", "x": "dot.x", "r": "dot.r + 0.5"},
    {"id": "label", "type": "text", "content": "Hello", "y": -1.6, "size": 0.4, "fill": "#dddddd"}
  ]
}
```

Object types and properties (every object needs a unique `id`; `opacity` on all):

| type   | properties |
|--------|-----------|
| circle | x y r fill stroke stroke_width |
| rect   | x y w h corner_radius rotation fill stroke stroke_width (x,y is the center) |
| line   | x1 y1 x2 y2 stroke stroke_width |
| text   | content font align max_width line_height (static) · x y size fill · newlines in content start new lines; max_width wraps at words |
| code   | content font char_width line_height theme spans[] (static) · x y size fill · monospace block, top-left at (x,y), fixed grid; `theme: "default"` highlights Python; use spaces not tabs |
| span   | only inside `code.spans`: line, token (+nth), chars (selectors, static) · fill background opacity · selects by line / Python token / char range; ids are global |
| group  | x y rotation scale children[] (children ids are global) |

Any numeric property accepts: a number · `"t"` · `"<id>.<prop>"` · shorthand `"0.2*sin(6*t)"` ·
an op node `{"op": "mul", "args": [...]}` · a tween. `fill`/`stroke` accept a color, `null`, or a tween with color keys.

Ops: `add sub mul div neg sin cos abs min max clamp smoothstep noise`. Shorthand knows `pi`, `tau`.
Tween: `{"op": "tween", "keys": [[t, v], ...], "ease": "..."}`; holds first/last value outside its keys.
Eases: `linear in_quad out_quad in_out_quad out_cubic in_out_cubic spring`.

See `reference.md` for recipes (fade in, staggered entrances, orbit, bounce, follow), the code-block section
(selectors, reveal line by line, highlight then let go), and taste notes.
