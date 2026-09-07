"""Python sugar example. Run: uv run python examples/bounce.py"""

from buttery import Circle, Line, Scene, T, Text, keyframes, sin, tween

dot = Circle("dot", r=0.3, fill="coral")
dot.x = tween(-3, 3, at=0, dur=1.5, ease="out_cubic")
dot.y = 0.2 * sin(6 * T)

ring = Circle("ring", fill=None, stroke="white", stroke_width=0.04)
ring.x = dot.ref.x
ring.r = dot.ref.r + 0.5
ring.opacity = keyframes({0: 0, 0.5: 1, 2.5: 1, 3: 0})

floor = Line("floor", x1=-3.5, y1=-0.6, x2=3.5, y2=-0.6, stroke="#444444", stroke_width=0.03)
label = Text("label", content="state(t) is a pure function", y=-1.6, size=0.4, fill="#cccccc")

scene = Scene(duration=3).add(dot, ring, floor, label)

if __name__ == "__main__":
    scene.save("examples/bounce.json")
    print(scene.state(1.0))
    scene.preview(1.0, path="examples/bounce_preview.png")
    print(scene.render("examples/bounce.mp4"))
