"""A physically shaped bounce with squash, built from clamp windows. Run: uv run python examples/squash_bounce.py

Each arc is a parabola  4*h*u*(1-u)  with u = clamp((t - start)/dur, 0, 1). It is zero outside its
window, so summing the arcs gives a piecewise ballistic path with no mod/floor ops. Peak height and
duration decay by the restitution e each bounce (h *= e^2, dur *= e), like a real ball.
"""

from buttery import Circle, Line, Rect, Scene, T, Text, clamp, smoothstep

# --- physics knobs ---------------------------------------------------------
FLOOR = -1.1        # y of the floor line
R = 0.32            # ball radius
DROP_H = 2.2        # release height above the floor
DROP_T = 0.62       # time to fall DROP_H (sets gravity)
E = 0.68            # coefficient of restitution
START = 0.4         # hold before release
BOUNCES = 6
SQUASH = 0.28       # squash at the first (hardest) impact, as a fraction of the diameter
SQUASH_T = 0.07     # half-width of the squash bump, seconds


def parabola(start: float, dur: float, peak: float):
    u = clamp((T - start) / dur, 0, 1)
    return 4 * peak * u * (1 - u)


def bump(center: float, width: float):
    """1 at `center`, smoothly 0 at |t - center| >= width."""
    return 1 - smoothstep(0, width, abs(T - center))


# release: half parabola from DROP_H down to the floor
v = clamp((T - START) / DROP_T, 0, 1)
height = DROP_H * (1 - v * v)
squash = 0
impacts = []

t0 = START + DROP_T
peak, dur, speed = DROP_H, 2 * DROP_T, 1.0
for _ in range(BOUNCES):
    impacts.append(t0)
    squash = squash + SQUASH * speed * bump(t0, SQUASH_T * (0.6 + 0.4 * speed))
    peak, dur, speed = peak * E * E, dur * E, speed * E
    height = height + parabola(t0, dur, peak)
    t0 += dur

# --- objects ----------------------------------------------------------------
floor = Line("floor", x1=-3.6, y1=FLOOR, x2=3.6, y2=FLOOR, stroke="#3a3a42", stroke_width=0.035)

dot = Rect("dot", fill="coral", corner_radius=R)   # a rounded rect with corner_radius = r is a circle
dot.w = 2 * R * (1 + squash)
dot.h = 2 * R * (1 - squash)
dot.x = clamp((T - START) / 3.0, 0, 1) * 5.2 - 2.6      # constant horizontal speed after release
dot.y = FLOOR + height + dot.ref.h / 2                   # bottom edge rides the floor while squashed

shadow = Circle("shadow", fill="#000000", y=FLOOR - 0.02)
shadow.x = dot.ref.x
shadow.r = 0.22 + 0.10 * clamp(height / DROP_H, 0, 1)
shadow.opacity = 0.55 - 0.45 * clamp(height / DROP_H, 0, 1)

label = Text("label", content="dot", size=0.26, fill="#1a1a1e")
label.x = dot.ref.x
label.y = dot.ref.y - 0.09                               # optical centre of the glyphs

caption = Text("caption", content="ballistic arcs from clamped parabolas, squash on impact",
               y=-1.75, size=0.3, fill="#8a8a94")

scene = Scene(duration=4, background="#0e0e11").add(floor, shadow, dot, label, caption)

if __name__ == "__main__":
    scene.save("examples/squash_bounce.json")
    print(scene.state(START + DROP_T))
    scene.preview(START + DROP_T, path="examples/squash_bounce_preview.png")
    print(scene.render("examples/squash_bounce.mp4"))
