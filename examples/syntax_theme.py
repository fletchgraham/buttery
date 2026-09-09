"""Every color of the syntax highlighter, side by side. Run: uv run python examples/syntax_theme.py

A `code` block's `theme` colors Python tokens by kind: keyword, name, number, string, op, comment. It is
a built-in name ("default") or a mapping from kind to color; kinds left out keep the block's `fill`. The
color is a fill layer between the block's `fill` and its spans, so it is not animatable on its own. To
compare themes, this scene stacks one block per theme at the same spot and crossfades their opacity:
first no theme at all, then the built-in default, then a custom theme that colors all six kinds. The
legend on the right shows each kind in the color the active theme gives it (or the ink color when the
theme leaves it alone), and a span pulses on the token the caption names so the legend and the code agree.
"""

from buttery import Code, Rect, Scene, Text, keyframes
from buttery.code import THEMES, TokenKind

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

BG, INK, MUTED, PANEL = "#0e0e11", "#e8e8ee", "#8a8a94", "#16161c"
KINDS: list[TokenKind] = ["keyword", "name", "number", "string", "op", "comment"]
# One example token per kind, so the legend can point at the code.
SAMPLE: dict[TokenKind, dict] = {
    "keyword": dict(token="def"), "name": dict(token="fib"), "number": dict(token="2"),
    "string": dict(line=10, chars=(6, 30)), "op": dict(token="->"), "comment": dict(line=1),
}
FULL: dict[TokenKind, str] = {  # a theme that gives every kind its own color, including name and op
    "keyword": "#ff7b72", "name": "#79c0ff", "number": "#f2cc60", "string": "#a5d6ff", "op": "#ff9bce",
    "comment": "#6e7681",
}
VIEWS: list[tuple[str, str | dict | None]] = [
    ("theme=None: every character is the block's fill", None),
    ('theme="default": keywords, numbers, strings, comments', "default"),
    ("theme={...}: a custom mapping colors all six kinds", FULL),
]
SIZE, HOLD, FADE, PULSE = 0.24, 3.6, 0.5, 0.15
T0 = 0.4


def window(t0: float, t1: float, low, high, ramp: float) -> list:
    """Hold `low`, ramp to `high` at t0, back to `low` at t1."""
    return [(t0, low), (t0 + ramp, high), (t1 - ramp, high), (t1, low)]


def theme_map(theme) -> dict[TokenKind, str]:
    return THEMES[theme] if isinstance(theme, str) else (theme or {})


panel = Rect("panel", x=-1.2, y=0.0, w=5.15, h=3.7, corner_radius=0.15, fill=PANEL)
objects = [panel]
for k, (caption, theme) in enumerate(VIEWS):
    t0, t1 = T0 + k * HOLD, T0 + (k + 1) * HOLD
    on = keyframes(window(t0, t1, 0, 1, FADE), ease="in_out_quad")
    colors = theme_map(theme)

    code = Code(f"code{k}", content=SRC, size=SIZE, fill=INK, theme=theme, opacity=on)
    code.x = panel.x - code.width / 2
    code.y = panel.y + code.height / 2
    # The legend walks the kinds one per beat; a background pulse on the sample token keeps them in step.
    step = (HOLD - 2 * FADE) / len(KINDS)
    for j, kind in enumerate(KINDS):
        p0 = t0 + FADE + j * step
        code.select(f"pulse{k}_{j}", **SAMPLE[kind],
                    background=keyframes(window(p0, p0 + step, "transparent", "#3a3a52", PULSE), ease="out_quad"))
    objects.append(code)

    x = 2.0
    objects.append(Text(f"head{k}", content="token kind", x=x, y=1.6, size=0.2, fill=MUTED, align="left", opacity=on))
    for j, kind in enumerate(KINDS):
        color = colors.get(kind, INK)
        y = 1.15 - j * 0.46
        p0 = t0 + FADE + j * step
        bump = keyframes(window(p0, p0 + step, 0.0, 0.12, PULSE), ease="out_quad")  # nudge right on its beat
        objects.append(Rect(f"swatch{k}_{j}", x=x + 0.12 + bump, y=y, w=0.24, h=0.24, corner_radius=0.05, fill=color, opacity=on))
        objects.append(Text(f"kind{k}_{j}", content=kind, x=x + 0.4 + bump, y=y, size=0.24, fill=color, align="left", opacity=on))
        objects.append(Text(f"hex{k}_{j}", content=color if kind in colors else "fill", x=x + 0.4 + bump, y=y - 0.21,
                            size=0.12, fill=MUTED, align="left", opacity=on))
    objects.append(Text(f"cap{k}", content=caption, y=-2.05, size=0.24, fill=MUTED, opacity=on))

title = Text("title", content="syntax highlighting: one theme per block", y=2.03, size=0.28, fill=INK)
END = T0 + len(VIEWS) * HOLD + 0.4
scene = Scene(duration=END, background=BG).add(title, *objects)

if __name__ == "__main__":
    scene.save("examples/syntax_theme.json")
    scene.preview(T0 + 2 * HOLD + HOLD / 2, path="examples/syntax_theme_preview.png")
    print(scene.render("examples/syntax_theme.mp4"))
