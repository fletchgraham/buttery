"""Every color of the syntax highlighter. Run: uv run python examples/syntax_theme.py

A `code` block's `theme` colors Python tokens by kind: keyword, name, number, string, op, comment. It is a
built-in name ("default") or a mapping from kind to color; kinds left out keep the block's `fill`. Here a custom
theme gives all six kinds a color, and a legend lists each kind in that color. The legend walks the kinds one
per beat: the swatch bumps out and, in the code, every token of that kind gets a background pulse. The tokens
come from `python_tokens`, the same tokenizer the theme uses, so the pulses and the colors always agree.
"""

from buttery import Code, Rect, Scene, Text, keyframes
from buttery.code import TokenKind, python_tokens

SRC = "\n".join([
    "# nth Fibonacci number, memoized",
    "from functools import cache",
    "",
    "@cache",
    "def fib(n: int = 0) -> int:",
    "    if n < 2:",
    "        return n",
    "    return fib(n - 1) + fib(n - 2)",
    "",
    'print(f"fib(10) = {fib(10):>3}")',
])

BG, INK, MUTED, PANEL, PULSE_BG = "#0e0e11", "#e8e8ee", "#8a8a94", "#16161c", "#3a3a52"
THEME: dict[TokenKind, str] = {
    "keyword": "#ff7b72", "name": "#79c0ff", "number": "#f2cc60", "string": "#a5d6ff", "op": "#ff9bce",
    "comment": "#6e7681",
}
KINDS = list(THEME)
SIZE, T0, HOLD, RAMP = 0.24, 0.8, 1.6, 0.25


def window(t0: float, t1: float, low, high) -> list:
    """Hold `low`, ramp to `high` at t0, back to `low` at t1. Before t0 the first key holds, so nothing shows."""
    return [(t0, low), (t0 + RAMP, high), (t1 - RAMP, high), (t1, low)]


panel = Rect("panel", x=-1.2, y=0.0, w=5.15, h=3.7, corner_radius=0.15, fill=PANEL)
code = Code("code", content=SRC, size=SIZE, fill=INK, theme=THEME)
code.x = panel.x - code.width / 2
code.y = panel.y + code.height / 2

legend = [Text("head", content="token kind", x=2.0, y=1.6, size=0.2, fill=MUTED, align="left")]
for j, kind in enumerate(KINDS):
    t0, t1 = T0 + j * HOLD, T0 + (j + 1) * HOLD
    # every token of this kind pulses together; chars are offsets into the whole snippet
    for i, tok in enumerate(t for t in python_tokens(SRC) if t.kind == kind):
        code.select(f"{kind}{i}", chars=(tok.start, tok.end),
                    background=keyframes(window(t0, t1, "transparent", PULSE_BG), ease="out_quad"))
    y = 1.15 - j * 0.46
    bump = keyframes(window(t0, t1, 0.0, 0.12), ease="out_quad")  # the swatch and label nudge right on their beat
    legend += [
        Rect(f"swatch_{kind}", x=2.12 + bump, y=y, w=0.24, h=0.24, corner_radius=0.05, fill=THEME[kind]),
        Text(f"kind_{kind}", content=kind, x=2.4 + bump, y=y, size=0.24, fill=THEME[kind], align="left"),
        Text(f"hex_{kind}", content=THEME[kind], x=2.4 + bump, y=y - 0.21, size=0.12, fill=MUTED, align="left"),
    ]

title = Text("title", content="syntax highlighting", y=2.03, size=0.28, fill=INK)
END = T0 + len(KINDS) * HOLD + 0.6
scene = Scene(duration=END, background=BG).add(title, panel, code, *legend)

if __name__ == "__main__":
    scene.save("examples/syntax_theme.json")
    scene.preview(T0 + HOLD / 2, path="examples/syntax_theme_preview.png")
    print(scene.render("examples/syntax_theme.mp4"))
