"""Walking through a function, one line at a time. Run: uv run python examples/code_walk.py

A `code` block lays its characters on a fixed grid (0.6 * size per column, line_height * size per row), so a
selection by line, by Python token, or by character range is just a run of cells. The function is revealed a
line per beat (one span per line, opacity 0 -> 1), then a caption walks through it. Each step selects the
part it talks about with spans: `fill` tweens the characters to the accent color and `background` tweens
from `transparent` to a highlight and back, so the highlight fades while the code underneath stays put.
"""

from buttery import Code, Scene, Text, keyframes

SRC = "\n".join([
    "def clamp(x, lo, hi):",
    "    if x < lo:",
    "        return lo",
    "    return min(x, hi)",
])

BG, INK, MUTED = "#0e0e11", "#e8e8ee", "#8a8a94"
ACCENT, HI_BG = "#e0a54a", "#2b2b3d"
SIZE = 0.34
REVEAL_AT, REVEAL_EACH, REVEAL_DUR = 0.6, 0.55, 0.45
HOLD, RAMP = 2.8, 0.3

code = Code("fn", content=SRC, size=SIZE, fill=INK)
code.x = -code.width / 2                 # the grid makes the block's size known without rendering
code.y = code.height / 2 + 0.3

# 1. reveal: one span per line, fading in on its beat
for n in range(1, code.rows + 1):
    t0 = REVEAL_AT + (n - 1) * REVEAL_EACH
    code.select(f"line{n}", line=n, opacity=keyframes([(t0, 0), (t0 + REVEAL_DUR, 1)], ease="out_quad"))

# 2. walkthrough: each step says what it selects, and how (token / chars / line)
T0 = REVEAL_AT + code.rows * REVEAL_EACH + 0.5
STEPS = [
    ("x is the value; lo and hi are the bounds",
     [dict(token="x", nth=i) for i in range(3)] + [dict(line=1, chars=(13, 19))]),
    ("below lo? hand back lo", [dict(line=2), dict(line=3)]),
    ("otherwise min(x, hi) caps it at hi", [dict(line=4, chars=(11, 21))]),
]


def window(t0: float, t1: float, low, high) -> list:
    """Hold `low`, ramp to `high` at t0, back to `low` at t1. Before t0 the first key holds, so nothing shows."""
    return [(t0, low), (t0 + RAMP, high), (t1 - RAMP, high), (t1, low)]


captions = []
for k, (text, selections) in enumerate(STEPS):
    t0, t1 = T0 + k * HOLD, T0 + (k + 1) * HOLD
    for j, sel in enumerate(selections):
        code.select(f"step{k}_{j}", **sel,
                    fill=keyframes(window(t0, t1, INK, ACCENT), ease="out_quad"),
                    background=keyframes(window(t0, t1, "transparent", HI_BG), ease="out_quad"))
    captions.append(Text(f"cap{k}", content=text, y=-1.5, size=0.3, fill=MUTED,
                         opacity=keyframes(window(t0, t1, 0, 1), ease="out_quad")))

title = Text("title", content="clamp, line by line", y=1.85, size=0.3, fill=INK)
END = T0 + len(STEPS) * HOLD + 0.8
scene = Scene(duration=END, background=BG).add(title, code, *captions)

if __name__ == "__main__":
    scene.save("examples/code_walk.json")
    scene.preview(T0 + HOLD * 1.5, path="examples/code_walk_preview.png")
    print(scene.render("examples/code_walk.mp4"))
