"""Compile expression trees to closures and evaluate a scene at time t."""

from __future__ import annotations

import bisect
from typing import TYPE_CHECKING, Any, Callable

from .color import lerp_color, parse_color, to_hex
from .easing import EASINGS
from .errors import EvalError, SceneError, SceneValidationError
from .expr import Op, Ref, Tween, deps
from .objects import Group, SceneObject, walk
from .ops import OP_FUNCS

if TYPE_CHECKING:
    from .scene import Scene

Env = dict[str, Any]
Fn = Callable[[Env], Any]


def compile_tween(tw: Tween) -> Fn:
    times = [k[0] for k in tw.keys]
    ease = EASINGS[tw.ease]
    n = len(times)
    if tw.is_color:
        colors = [parse_color(k[1]) for k in tw.keys]  # type: ignore[arg-type]

        def color_fn(env: Env) -> str:
            t = env["t"]
            if t <= times[0]:
                return to_hex(colors[0])
            if t >= times[-1]:
                return to_hex(colors[-1])
            i = bisect.bisect_right(times, t) - 1
            t0, t1 = times[i], times[i + 1]
            p = 1.0 if t1 == t0 else ease((t - t0) / (t1 - t0))
            return to_hex(lerp_color(colors[i], colors[i + 1], p))

        return color_fn

    vals = [float(k[1]) for k in tw.keys]  # type: ignore[arg-type]

    def num_fn(env: Env) -> float:
        t = env["t"]
        if t <= times[0]:
            return vals[0]
        if t >= times[-1]:
            return vals[-1]
        i = bisect.bisect_right(times, t) - 1
        if i >= n - 1:
            return vals[-1]
        t0, t1 = times[i], times[i + 1]
        p = 1.0 if t1 == t0 else ease((t - t0) / (t1 - t0))
        v0, v1 = vals[i], vals[i + 1]
        return v0 + (v1 - v0) * p

    return num_fn


def compile_expr(expr: Any) -> Fn:
    if isinstance(expr, (int, float)):
        c = float(expr)
        return lambda env: c
    if isinstance(expr, str):  # static color / static string
        return lambda env: expr
    if expr is None:
        return lambda env: None
    if isinstance(expr, Ref):
        key = expr.path
        return lambda env: env[key]
    if isinstance(expr, Tween):
        return compile_tween(expr)
    if isinstance(expr, Op):
        fns = [compile_expr(a) for a in expr.args]
        func = OP_FUNCS[expr.op]
        if len(fns) == 1:
            f0 = fns[0]
            return lambda env: func(f0(env))
        if len(fns) == 2:
            f0, f1 = fns
            return lambda env: func(f0(env), f1(env))
        return lambda env: func(*[f(env) for f in fns])
    raise TypeError(f"cannot compile {type(expr).__name__}")


class CompiledScene:
    """A scene with every animatable property compiled and topologically ordered.

    `state(t)` is a pure function: it builds a fresh env each call and never mutates the scene.
    """

    def __init__(self, scene: "Scene") -> None:
        self.scene = scene
        errors = scene.check()
        if errors:
            raise SceneValidationError(errors)
        nodes: dict[str, tuple[SceneObject, str, Fn, set[str]]] = {}
        for obj, _ in walk(scene.objects):
            for prop in type(obj).animatable():
                expr = getattr(obj, prop)
                nodes[f"{obj.id}.{prop}"] = (obj, prop, compile_expr(expr), deps(expr))
        self.order = _topo_order(nodes)
        self.nodes = nodes

    def env(self, t: float) -> Env:
        env: Env = {"t": float(t)}
        nodes = self.nodes
        for key in self.order:
            obj, prop, fn, _ = nodes[key]
            try:
                env[key] = fn(env)
            except EvalError:
                raise
            except Exception as exc:  # noqa: BLE001 - convert everything to a located error
                raise EvalError(obj.id, prop, t, f"{type(exc).__name__}: {exc}") from None
        return env

    def state(self, t: float) -> dict[str, Any]:
        env = self.env(t)
        return {"t": float(t), "objects": [self._resolve(o, env) for o in self.scene.objects]}

    def _resolve(self, obj: SceneObject, env: Env) -> dict[str, Any]:
        cls = type(obj)
        out: dict[str, Any] = {"id": obj.id, "type": obj.type}
        for prop in cls.animatable():
            out[prop] = env[f"{obj.id}.{prop}"]
        for prop in cls.static_props():
            out[prop] = getattr(obj, prop)
        if isinstance(obj, Group):
            out["children"] = [self._resolve(c, env) for c in obj.children]
        return out


def _topo_order(nodes: dict[str, tuple[SceneObject, str, Fn, set[str]]]) -> list[str]:
    indeg = {k: len(v[3]) for k, v in nodes.items()}
    dependents: dict[str, list[str]] = {k: [] for k in nodes}
    for k, v in nodes.items():
        for d in v[3]:
            dependents[d].append(k)
    ready = [k for k, n in indeg.items() if n == 0]
    order: list[str] = []
    while ready:
        k = ready.pop()
        order.append(k)
        for d in dependents[k]:
            indeg[d] -= 1
            if indeg[d] == 0:
                ready.append(d)
    if len(order) != len(nodes):  # unreachable if Scene.check() passed, but keep the guard
        stuck = sorted(k for k, n in indeg.items() if n > 0)
        raise SceneValidationError([SceneError(path=stuck[0], message=f"dependency cycle among: {', '.join(stuck)}")])
    return order


__all__ = ["CompiledScene", "compile_expr", "compile_tween"]
