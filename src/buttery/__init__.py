"""Agent-friendly 2D explainer animations. The scene is a pure function of time.

    from buttery import *

    dot = Circle("dot", r=0.3, fill="coral")
    dot.x = tween(-3, 3, at=0, dur=1.5, ease="out_cubic")
    dot.y = 0.2 * sin(6 * T)
    ring = Circle("ring", fill=None, stroke="white")
    ring.r = dot.ref.r + 0.5

    scene = Scene(duration=3).add(dot, ring)
    scene.state(1.0)          # plain data
    scene.render("out.mp4")   # ffmpeg, motion blur on by default
"""

from .errors import EvalError, RenderError, SceneError, SceneValidationError
from .expr import Op, Ref, T, Tween, clamp, cos, keyframes, max_, min_, noise, ref, sin, smoothstep, tween
from .objects import Circle, Code, Group, Line, Rect, SceneObject, Span, Text
from .scene import Scene

__version__ = "0.1.0"

__all__ = [
    "Circle", "Code", "EvalError", "Group", "Line", "Op", "Rect", "Ref", "RenderError", "Scene", "SceneError",
    "SceneObject", "SceneValidationError", "Span", "T", "Text", "Tween", "clamp", "cos", "keyframes", "max_", "min_",
    "noise", "ref", "sin", "smoothstep", "tween",
]
