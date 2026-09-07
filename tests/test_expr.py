import math

import pytest
from pydantic import ValidationError

from buttery import Op, Ref, T, Tween, keyframes, sin, tween
from buttery.easing import EASINGS
from buttery.evaluate import compile_expr
from buttery.parse import parse_expr


def ev(expr, t=0.0, **env):
    return compile_expr(expr)({"t": t, **env})


def test_operator_overloading_builds_tree():
    e = 0.2 * sin(6 * T) + Ref("dot.r")
    assert e.model_dump() == {
        "op": "add",
        "args": [{"op": "mul", "args": [0.2, {"op": "sin", "args": [{"op": "mul", "args": [6.0, "t"]}]}]}, "dot.r"],
    }


def test_python_and_json_agree():
    py = 0.2 * sin(6 * T)
    js = Op.model_validate({"op": "mul", "args": [0.2, {"op": "sin", "args": [{"op": "mul", "args": [6, "t"]}]}]})
    assert py == js
    assert ev(py, 0.3) == pytest.approx(0.2 * math.sin(1.8))


def test_shorthand_parses_to_same_tree():
    assert parse_expr("0.2 * sin(6*t)") == 0.2 * sin(6 * T)
    assert parse_expr("dot.r + 0.5") == Ref("dot.r") + 0.5
    assert parse_expr("t") == T
    assert parse_expr("-t") == -T


def test_shorthand_folds_constants_and_knows_pi():
    assert parse_expr("2*pi") == pytest.approx(math.tau)
    assert parse_expr("(1 + 2) * 3") == 9.0
    node = parse_expr("1/0")  # not folded, errors at eval with a location
    assert isinstance(node, Op)


@pytest.mark.parametrize("bad", ["foo + 1", "sin(", "2 +", "1 $ 2", "tan(t)", "clamp(t)", ""])
def test_shorthand_errors(bad):
    with pytest.raises(ValueError):
        parse_expr(bad)


def test_arity_checked():
    with pytest.raises(ValidationError):
        Op(op="clamp", args=[1])
    with pytest.raises(ValidationError):
        Op(op="neg", args=[1, 2])
    with pytest.raises(ValidationError):
        Op(op="pow", args=[1, 2])


def test_variadic_ops():
    assert ev(Op(op="add", args=[1, 2, 3])) == 6
    assert ev(Op(op="max", args=[1, 5, 3])) == 5


def test_math_ops():
    assert ev(parse_expr("clamp(5, 0, 1)")) == 1
    assert ev(parse_expr("smoothstep(0, 1, 0.5)")) == 0.5
    assert ev(parse_expr("abs(-3)")) == 3
    n1, n2 = ev(parse_expr("noise(t)"), 0.37), ev(parse_expr("noise(t)"), 0.37)
    assert n1 == n2 and -1 <= n1 <= 1
    assert ev(parse_expr("noise(t)"), 0.37) != ev(parse_expr("noise(t, 7)"), 0.37)


def test_tween_holds_and_eases():
    tw = tween(-3, 3, at=1, dur=2, ease="out_cubic")
    assert tw.model_dump() == {"op": "tween", "keys": [(1.0, -3.0), (3.0, 3.0)], "ease": "out_cubic"}
    f = compile_expr(tw)
    assert f({"t": 0}) == -3
    assert f({"t": 1}) == -3
    assert f({"t": 3}) == 3
    assert f({"t": 9}) == 3
    assert f({"t": 2}) == pytest.approx(-3 + 6 * EASINGS["out_cubic"](0.5))


def test_keyframes_multi_segment_and_dict():
    tw = keyframes({0: 0, 1: 1, 2: 0})
    f = compile_expr(tw)
    assert f({"t": 0.5}) == 0.5
    assert f({"t": 1.5}) == 0.5
    assert keyframes([(0, 0), (1, 1)]) == keyframes({0: 0, 1: 1})


def test_tween_validation():
    with pytest.raises(ValidationError, match="sorted"):
        Tween(keys=[(1, 0), (0, 1)])
    with pytest.raises(ValidationError, match="all numbers or all colors"):
        Tween(keys=[(0, 0), (1, "red")])
    with pytest.raises(ValidationError, match="invalid color"):
        Tween(keys=[(0, "reddish"), (1, "blue")])


def test_color_tween():
    f = compile_expr(keyframes([(0, "#000000"), (1, "#ffffff")]))
    assert f({"t": 0.5}) == "#808080"
    assert f({"t": 5}) == "#ffffff"
    assert compile_expr(keyframes([(0, "red"), (1, "#0000ff80")]))({"t": 1}) == "#0000ff80"


def test_easings_hit_endpoints():
    for name, fn in EASINGS.items():
        assert fn(0.0) == pytest.approx(0.0, abs=1e-9), name
        assert fn(1.0) == pytest.approx(1.0, abs=1e-9), name


def test_tween_participates_in_arithmetic():
    e = tween(0, 1) * 2 + T
    assert ev(e, 0.5) == pytest.approx(1.5)
