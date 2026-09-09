# Agents

buttery was built so that an AI agent can be the primary author. The agent writes JSON, and four tools give
it everything it needs to check its work: `validate`, `state`, `preview`, `render`. They are available as a
CLI, as Python functions, and as an MCP server, and every one of them returns JSON, never a bare stack trace.

## CLI

```bash
buttery validate scene.json                 # ok, or structured errors
buttery state scene.json --t 1.25           # every property resolved at t
buttery preview scene.json --t 1.25 --out p.png --scale 0.25
buttery render scene.json out.mp4 [--no-motion-blur --samples 8 --shutter 0.5 --workers N]
buttery render scene.json frames/           # PNG sequence, no ffmpeg needed
buttery schema                              # the Scene JSON schema
buttery mcp                                 # MCP server on stdio
```

`validate` also reads a scene from stdin with `-`. Without an install, prefix any of these with `uvx`:
`uvx buttery validate scene.json`.

Every call prints one JSON object:

```json
{"ok": true, "objects": ["dot", "ring", "label"], "duration": 3, "fps": 60, "frames": 180, "size": [1920, 1080]}
```

```json
{"ok": false, "errors": [
  {"path": "objects[1].x", "message": "reference 'dott.x': no object with id 'dott'",
   "object": "ring", "property": "x", "t": null}
]}
```

Errors name the `path` in the JSON, the `object` id, the `property`, and, for evaluation errors, the `t` at
which they happened. That is enough for an agent to fix the scene and re-validate without reading any source.

## The loop

1. Sketch the beats: what moves when, in seconds. Default duration 5 s, 60 fps, 1920×1080.
2. Write `scene.json`. Prefer `tween` for staged motion and expressions for continuous motion.
3. `validate`, then `preview` at two or three key times and look at the PNGs to check composition.
4. `render` to an `.mp4`.

`state` is the debugging tool in between: when something looks wrong at 2.3 s, the resolved values at 2.3 s
are one command away, because the scene is a pure function of time.

## MCP server

`buttery mcp` serves the same four tools over stdio, plus a `scene://schema` resource. Register it with
Claude Code from the published packages, no checkout needed:

```bash
claude mcp add buttery -- npx -y buttery-mcp
```

The [`buttery-mcp`](https://www.npmjs.com/package/buttery-mcp) npm shim runs `uvx buttery mcp`, so it needs
`uv` on the path and nothing else. From a clone:

```bash
claude mcp add buttery -- uv run --directory /path/to/buttery buttery mcp
```

## Claude Code skill

The repository ships a skill in [`skill/`](https://github.com/fletchgraham/buttery/tree/main/skill). It
teaches Claude the scene format, the loop above, a table of primitives, and a page of recipes and taste
notes. Symlink or copy it into your skills directory:

```bash
ln -s /path/to/buttery/skill ~/.claude/skills/buttery
```

Then ask for an explainer:

```
❯ Use buttery to make an animated explainer of merging two sorted lists.
```

The skill runs buttery from your working directory, so `scene.json`, previews, and the rendered video land
where you are.

## Python

The tool functions in `buttery.tools` take a dict or JSON string and return a dict of the same shape the
CLI prints:

```python
from buttery import tools

tools.validate(scene_dict)
tools.state(scene_dict, t=1.25)
tools.preview(scene_dict, t=1.25, scale=0.25, path="p.png")   # also returns png_base64
tools.render(scene_dict, "out.mp4")
```

This is the layer the CLI and the MCP server are built on, and it is the one to reuse if you are wiring
buttery into your own agent.
