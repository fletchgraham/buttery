# Install

```bash
pip install buttery    # or: uv add buttery
brew install ffmpeg    # for .mp4 output (PNG sequences work without it)
```

buttery needs Python 3.11 or newer. The renderer is [skia-python](https://github.com/kyamagu/skia-python),
which ships large platform wheels, so expect a heavier install than the code size suggests.

## No install at all

`uvx` runs the CLI straight from PyPI:

```bash
uvx buttery validate scene.json
uvx buttery render scene.json out.mp4
```

This is also how the [Claude Code skill](agents.md#claude-code-skill) and the
[`buttery-mcp`](https://www.npmjs.com/package/buttery-mcp) npm shim find buttery when it is not on your path.

## From a clone

```bash
git clone https://github.com/fletchgraham/buttery
cd buttery
uv sync                # Python 3.11+, pydantic, skia-python, numpy, mcp
uv run pytest
uv run buttery --help
```

## ffmpeg

`render` writes an `.mp4` (or `.mov`) by piping frames to ffmpeg. Without ffmpeg, pass a directory instead of
a file and you get a numbered PNG sequence:

```bash
buttery render scene.json frames/
```

## Check it works

```bash
echo '{"duration": 1, "objects": [{"id": "dot", "type": "circle", "fill": "coral"}]}' > scene.json
buttery validate scene.json
buttery preview scene.json --t 0.5 --out p.png --scale 0.25
```

`validate` prints `{"ok": true, ...}` and `preview` writes a quarter-scale PNG of a coral dot at the center of
a dark frame.
