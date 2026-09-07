# buttery-mcp

Launcher for the [buttery](https://github.com/fletchgraham/buttery) MCP server. Buttery makes agent-friendly 2D
explainer animations: the scene is a pure function of time, JSON is the contract, and the MCP server exposes
`validate`, `state`, `preview`, and `render` tools plus a `scene://schema` resource.

The server itself is Python (`pip install buttery`). This package is a thin stdio shim so MCP clients can use `npx`.

## Requirements

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/) (used as `uvx buttery mcp`), or `buttery` installed on your PATH
- `ffmpeg` for `.mp4` output (PNG sequences work without it)

## Usage

Claude Code:

```bash
claude mcp add buttery -- npx -y buttery-mcp
```

Generic MCP client config:

```json
{ "mcpServers": { "buttery": { "command": "npx", "args": ["-y", "buttery-mcp"] } } }
```

## License

MIT
