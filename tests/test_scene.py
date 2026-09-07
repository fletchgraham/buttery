import json

import pytest

from buttery import Circle, EvalError, Group, Line, Rect, Scene, SceneValidationError, T, Text, keyframes, sin, tween


def make_scene():
    dot = Circle("dot", r=0.3, fill="coral")
    dot.x = tween(-3, 3, at=0, dur=1.5, ease="out_cubic")
    dot.y = 0.2 * sin(6 * T)
    ring = Circle("ring", fill=None, stroke="white")
    ring.r = dot.ref.r + 0.5
    ring.fill = keyframes([(0, "red"), (2, "blue")])
    label = Text("label", content="hi", y=-1.5)
    g = Group("g", rotation="45*t", children=[Rect("box", w=0.5, h=0.5, x="dot.x")])
    return Scene(duration=3).add(dot, ring, label, g)


def test_state_is_plain_data_in_dependency_order():
    st = make_scene().state(1.0)
    assert st["t"] == 1.0
    by_id = {o["id"]: o for o in st["objects"]}
    assert by_id["ring"]["r"] == pytest.approx(0.8)
    assert by_id["dot"]["x"] == pytest.approx(2.7777777)
    assert by_id["ring"]["fill"] == "#800080"
    assert by_id["g"]["rotation"] == 45.0
    assert by_id["g"]["children"][0]["x"] == by_id["dot"]["x"]
    assert by_id["label"]["content"] == "hi"
    json.dumps(st)  # serializable


def test_state_is_pure():
    scene = make_scene()
    a = scene.state(0.4)
    scene.state(2.9)
    assert scene.state(0.4) == a
    assert scene.find("dot").x.keys[0] == (0.0, -3.0)  # unchanged


def test_json_roundtrip():
    scene = make_scene()
    js = scene.to_json()
    again = Scene.from_json(js)
    assert again == scene
    assert again.state(0.7) == scene.state(0.7)
    assert json.loads(js)["objects"][0]["y"]["op"] == "mul"


def test_positional_id_and_ref_proxy():
    c = Circle("c", r=1)
    assert c.id == "c"
    assert c.ref.r.path == "c.r"
    with pytest.raises(AttributeError, match="no animatable property"):
        c.ref.radius
    with pytest.raises(AttributeError, match="only numeric"):
        c.ref.fill


def test_assignment_parses_strings():
    c = Circle("c")
    c.x = "2 * t"
    assert c.x.op == "mul"
    with pytest.raises(Exception):
        c.x = "nope + 1"


def errors_of(data):
    with pytest.raises(SceneValidationError) as info:
        Scene.from_json(data)
    return info.value.errors


def test_duplicate_ids():
    errs = errors_of({"duration": 1, "objects": [{"id": "a", "type": "circle"}, {"id": "a", "type": "rect"}]})
    assert errs[0].path == "objects[1].id"
    assert "duplicate id 'a'" in errs[0].message


def test_missing_reference_names_object_and_property():
    errs = errors_of({"duration": 1, "objects": [{"id": "a", "type": "circle", "x": "b.x + 1"}]})
    e = errs[0]
    assert (e.path, e.object, e.property) == ("objects[0].x", "a", "x")
    assert "no object with id 'b'" in e.message


def test_bad_property_reference_lists_available():
    errs = errors_of({"duration": 1, "objects": [{"id": "a", "type": "circle"}, {"id": "b", "type": "line", "x1": "a.radius"}]})
    assert "no animatable property 'radius'" in errs[0].message
    assert "r," in errs[0].message


def test_cycle_rejected():
    errs = errors_of({
        "duration": 1,
        "objects": [{"id": "a", "type": "circle", "x": "b.x"}, {"id": "b", "type": "circle", "x": "c.y"}, {"id": "c", "type": "circle", "y": "a.x"}],
    })
    assert "dependency cycle" in errs[0].message
    assert "a.x -> b.x -> c.y -> a.x" in errs[0].message


def test_self_reference_is_a_cycle():
    errs = errors_of({"duration": 1, "objects": [{"id": "a", "type": "circle", "x": "a.x + 1"}]})
    assert "cycle" in errs[0].message


def test_color_tween_kind_mismatch():
    errs = errors_of({"duration": 1, "objects": [{"id": "a", "type": "circle", "fill": {"op": "tween", "keys": [[0, 1], [1, 2]]}}]})
    assert "color keys" in errs[0].message
    errs = errors_of({"duration": 1, "objects": [{"id": "a", "type": "circle", "r": {"op": "tween", "keys": [[0, "red"], [1, "blue"]]}}]})
    assert "numeric keys" in errs[0].message


def test_structural_errors_have_clean_paths():
    errs = errors_of({
        "duration": 1,
        "objects": [{"id": "a", "type": "blob"}, {"id": "b", "type": "text", "x": "2 +", "fill": 3}],
        "extra": 1,
    })
    paths = {e.path: e for e in errs}
    assert "objects[0]" in paths and paths["objects[0]"].object == "a"
    assert paths["objects[1].x"].object == "b" and paths["objects[1].x"].property == "x"
    assert "objects[1].fill" in paths
    assert "extra" in paths


def test_unknown_field_rejected():
    errs = errors_of({"duration": 1, "objects": [{"id": "a", "type": "circle", "radius": 2}]})
    assert errs[0].path == "objects[0].radius"


def test_invalid_json_text():
    errs = errors_of("{not json")
    assert "invalid JSON" in errs[0].message


def test_eval_error_names_object_property_and_t():
    scene = Scene.from_json({"duration": 1, "objects": [{"id": "a", "type": "circle", "x": {"op": "div", "args": [1, "t"]}}]})
    assert scene.state(0.5)["objects"][0]["x"] == 2
    with pytest.raises(EvalError) as info:
        scene.state(0.0)
    e = info.value.error
    assert (e.object, e.property, e.t) == ("a", "x", 0.0)
    assert "division by zero" in e.message


def test_python_incremental_build_is_checked_on_compile():
    scene = Scene(duration=1)
    scene.add(Circle("a", x="b.x"))
    with pytest.raises(SceneValidationError):
        scene.state(0)
    scene.add(Circle("b"))
    assert scene.state(0)["objects"][0]["x"] == 0.0


def test_defaults_and_frame_count():
    s = Scene(duration=2.5)
    assert s.size == (1920, 1080) and s.fps == 60 and s.frame_count == 150
    assert Scene(duration=1, fps=24).frame_count == 24


def test_json_schema_is_publishable():
    schema = Scene.json_schema()
    assert schema["properties"]["objects"]["items"]
    assert {"Circle", "Rect", "Line", "Text", "Group", "Op", "Tween"} <= set(schema["$defs"])
    json.dumps(schema)


def test_nested_group_ids_are_global():
    s = Scene(duration=1).add(Group("g", children=[Circle("inner")]), Circle("outer", r="inner.r"))
    assert s.state(0)["objects"][1]["r"] == 0.5
