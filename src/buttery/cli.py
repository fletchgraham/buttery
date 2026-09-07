"""Command line: buttery validate|state|preview|render|schema|mcp"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import tools


def _read_scene(arg: str) -> str:
    if arg == "-":
        return sys.stdin.read()
    return Path(arg).read_text()


def _emit(result: dict[str, Any], drop: tuple[str, ...] = ()) -> int:
    shown = {k: v for k, v in result.items() if k not in drop}
    print(json.dumps(shown, indent=2))
    return 0 if result.get("ok", True) else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="buttery", description="Agent-friendly 2D explainer animations.")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("validate", help="check a scene JSON file")
    s.add_argument("scene", help="scene .json path, or - for stdin")

    s = sub.add_parser("state", help="resolve all properties at time t")
    s.add_argument("scene")
    s.add_argument("--t", type=float, default=0.0)

    s = sub.add_parser("preview", help="write a low-res PNG at time t")
    s.add_argument("scene")
    s.add_argument("--t", type=float, default=0.0)
    s.add_argument("--scale", type=float, default=0.25)
    s.add_argument("--out", default="preview.png")

    s = sub.add_parser("render", help="render to .mp4/.mov or a PNG directory")
    s.add_argument("scene")
    s.add_argument("out")
    s.add_argument("--no-motion-blur", action="store_true")
    s.add_argument("--samples", type=int, default=8)
    s.add_argument("--shutter", type=float, default=0.5)
    s.add_argument("--workers", type=int, default=None)

    sub.add_parser("schema", help="print the Scene JSON schema")
    sub.add_parser("mcp", help="run the MCP server on stdio")

    a = p.parse_args(argv)

    if a.cmd == "validate":
        return _emit(tools.validate(_read_scene(a.scene)))
    if a.cmd == "state":
        return _emit(tools.state(_read_scene(a.scene), a.t))
    if a.cmd == "preview":
        return _emit(tools.preview(_read_scene(a.scene), a.t, a.scale, path=a.out), drop=("png_base64",))
    if a.cmd == "render":
        return _emit(
            tools.render(
                _read_scene(a.scene), a.out, motion_blur=not a.no_motion_blur,
                samples=a.samples, shutter=a.shutter, workers=a.workers,
            )
        )
    if a.cmd == "schema":
        print(json.dumps(tools.schema(), indent=2))
        return 0
    if a.cmd == "mcp":
        from .mcp_server import run

        run()
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
