# How v1 was written

Order of work, bottom up. Each step was smoke-tested before the next.

1. **Read the spec, check the toolchain.** uv, Python 3.13, ffmpeg, and whether skia-python has a macOS arm64 wheel. Spun up a scratch venv and drew one circle with skia to confirm array export and PNG encoding. Discovered the MCP SDK is 2.x (`MCPServer`, not `FastMCP`).

2. **Scaffold.** `pyproject.toml` (hatchling, `src/` layout, `animator` console script), `.python-version`, `.gitignore`, `uv sync`.

3. **Leaf modules, no dependencies.**
   - `color.py`: hex and CSS-name parsing, lerp, hex output, a pydantic `Color` type.
   - `easing.py`: the seven easing curves.
   - `ops.py`: numeric implementations and arity table for the op vocabulary, including the 1D value noise.

4. **Expression AST** (`expr.py`). `Ref`, `Op`, `Tween` as pydantic models with a shared operator-overloading mixin so `0.2 * sin(6 * T)` builds the same tree as the JSON. `Expr` is a discriminated union with a before-validator that parses strings. Sugar functions (`T`, `sin`, `tween`, `keyframes`, ...) and `deps()`.

5. **Shorthand parser** (`parse.py`). Tokenizer plus recursive descent for `+ - * /`, unary minus, calls, `pi`/`tau`, references. Folds constant sub-expressions.
   *Smoke test here:* Python vs JSON trees equal, parse errors readable. Hit and fixed a forward-ref problem by defining `Expr` after the node classes.

6. **Objects and scene.**
   - `errors.py`: `SceneError` (path, message, object, property, t) and conversion of pydantic errors into that shape.
   - `objects.py`: `Circle Rect Line Text Group`, positional `id`, `obj.ref.prop` proxy, `animatable()` introspection via a `Kind` marker in the annotations.
   - `evaluate.py`: compile each expression to a closure, topological order, `CompiledScene.state(t)`.
   - `scene.py`: `Scene` model, `check()` for ids / references / cycles / tween kinds, JSON load and save, `state()`.
   *Smoke test here:* state at t, JSON round trip, every error class.

7. **Renderer** (`render.py`). Skia rasterizer in world units with y up, fill/stroke paints, cap-height-centered text, group transforms, sub-frame motion blur, PNG encode, parallel render with a process pool, ffmpeg for mp4. Looked at a preview and a blurred frame to confirm orientation and blur.

8. **Agent surface.** `tools.py` (four functions, JSON in and out, all exceptions caught into structured errors), `cli.py`, `mcp_server.py`. Ran a full mp4 render from the CLI and listed tools through the MCP server in-process.

9. **Tests** (`tests/`): expressions and parser, scene validation and evaluation, rendering and tools. Fixed the deprecated default typeface with a font fallback chain.

10. **Examples, skill, README.** `examples/bounce.py`, `examples/launch_demo.json`, `skill/SKILL.md` and `reference.md`, this file.

- **Renamed to `buttery`** (2026-09-07). Package dir, pyproject name/script, imports, CLI, skill, README, examples, tests. The `animator` references above are historical.
