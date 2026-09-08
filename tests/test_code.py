import numpy as np
import pytest

from buttery import Code, Scene, SceneValidationError, Span, tween
from buttery.code import python_tokens, resolve_selection
from buttery.render import Rasterizer

SRC = "def f(x):\n    return x + 1  # done"


def test_tokens_have_kinds_and_character_offsets():
    toks = python_tokens(SRC)
    assert [(t.kind, t.text) for t in toks[:3]] == [("keyword", "def"), ("name", "f"), ("op", "(")]
    ret = next(t for t in toks if t.text == "return")
    assert (ret.start, ret.end, ret.line) == (14, 20, 2) and SRC[ret.start:ret.end] == "return"
    assert toks[-1].kind == "comment" and SRC[toks[-1].start:toks[-1].end] == "# done"
    assert {t.kind for t in toks} == {"keyword", "name", "op", "number", "comment"}


def test_resolve_by_line_token_and_chars():
    assert resolve_selection(SRC, line=1) == (0, 9)
    assert resolve_selection(SRC, token="x") == (6, 7)
    assert resolve_selection(SRC, token="x", nth=1) == resolve_selection(SRC, token="x", nth=-1) == (21, 22)
    assert resolve_selection(SRC, line=2, token="x") == (21, 22)  # line narrows the search
    assert resolve_selection(SRC, chars=(0, 3)) == (0, 3)
    assert resolve_selection(SRC, line=2, chars=(4, 10)) == (14, 20)  # columns on that line
    assert SRC[14:20] == "return"


def test_resolve_errors_name_the_problem():
    with pytest.raises(ValueError, match="line 5 is out of range"):
        resolve_selection(SRC, line=5)
    with pytest.raises(ValueError, match="no token 'y'"):
        resolve_selection(SRC, token="y")
    with pytest.raises(ValueError, match="no token 'return' on line 1"):
        resolve_selection(SRC, line=1, token="return")
    with pytest.raises(ValueError, match="occurs 2 time"):
        resolve_selection(SRC, token="x", nth=2)
    with pytest.raises(ValueError, match="out of range"):
        resolve_selection(SRC, line=1, chars=(0, 50))
    with pytest.raises(ValueError, match="cannot tokenize"):
        resolve_selection("s = 'open", token="s")
    assert resolve_selection("s = 'open", line=1) == (0, 9)  # line and chars never need valid Python


def test_select_sugar_validates_early_and_state_shows_the_range():
    code = Code("c", content=SRC, size=0.3)
    kw = code.select("kw", token="return", fill="coral")
    ln = code.select("l1", line=1, background="#333", opacity=tween(0, 1))
    assert isinstance(kw, Span) and code.spans == [kw, ln]
    with pytest.raises(ValueError, match="no token 'nope'"):
        code.select("bad", token="nope")
    assert len(code.spans) == 2
    spans = Scene(duration=1).add(code).state(0.5)["objects"][0]["spans"]
    assert (spans[0]["start"], spans[0]["end"]) == (14, 20) and spans[0]["fill"] == "coral"
    assert (spans[1]["start"], spans[1]["end"]) == (0, 9) and spans[1]["opacity"] == 0.5


def test_span_ids_are_scene_wide_and_referenceable():
    code = Code("c", content=SRC)
    code.select("kw", token="def")
    with pytest.raises(ValueError, match="duplicate id"):  # pydantic ValidationError at construction
        Scene(duration=1, objects=[code, Code("kw", content="x")])
    scene = Scene(duration=1).add(code)
    assert scene.find("kw").token == "def"
    assert code.spans[0].ref.opacity.path == "kw.opacity"


def test_json_roundtrip_and_structured_errors():
    code = Code("c", content=SRC, size=0.3)
    code.select("kw", token="def", fill="coral")
    scene = Scene(duration=1).add(code)
    again = Scene.from_json(scene.to_json())
    assert again == scene and again.state(0) == scene.state(0)

    def load(spans, content="x = 1"):
        return Scene.from_json({"duration": 1, "objects": [{"id": "c", "type": "code", "content": content, "spans": spans}]})

    with pytest.raises(SceneValidationError) as exc:
        load([{"id": "s", "line": 3}])
    (err,) = exc.value.errors
    assert err.path == "objects[0].spans[0]" and err.object == "s" and "line 3" in err.message
    with pytest.raises(SceneValidationError, match="line, token, chars"):
        load([{"id": "s"}])
    with pytest.raises(SceneValidationError, match="not tabs"):
        load([], content="\tx = 1")
    with pytest.raises(SceneValidationError):
        Scene.from_json({"duration": 1, "objects": [{"id": "s", "type": "span", "line": 1}]})  # not a top-level type


def test_geometry_is_a_pure_function_of_content():
    code = Code("c", content="ab\ncdef", size=0.5)
    assert (code.rows, code.cols) == (2, 4)
    assert code.width == pytest.approx(4 * 0.6 * 0.5) and code.height == pytest.approx(2 * 1.4 * 0.5)
    code.size = tween(0.2, 0.4)
    code.x = -code.width / 2  # still works when size is an expression
    assert Scene(duration=1).add(code).state(1.0)["objects"][0]["x"] == pytest.approx(-4 * 0.6 * 0.4 / 2)


def _cells():
    """'ab' at size 1, block top-left at (-0.6, 0.7): 320x180 px, 40 px/unit -> two 24x56 px cells."""
    a = (slice(62, 118), slice(136, 160))
    b = (slice(62, 118), slice(160, 184))
    return a, b


def _frame(code):
    scene = Scene(duration=1, size=(320, 180), background="black", objects=[code])
    return Rasterizer(scene.compile(), 320, 180).frame(0, motion_blur=False)[..., :3]  # RGB, alpha is always 255


def test_glyphs_land_on_the_grid_and_spans_restyle_their_cells():
    code = Code("c", content="ab", size=1.0, x=-0.6, y=0.7)
    code.select("s", chars=(1, 2), fill="red", background="blue")
    img = _frame(code)
    a, b = _cells()
    white = (img[..., 0] > 200) & (img[..., 1] > 200) & (img[..., 2] > 200)
    red = (img[..., 0] > 200) & (img[..., 1] < 60) & (img[..., 2] < 60)
    blue = (img[..., 2] > 200) & (img[..., 0] < 60)
    assert white[a].any() and not red[a].any() and not blue[a].any()
    assert red[b].any() and not white[b].any()
    assert tuple(img[63, 182, :3]) == (0, 0, 255)  # background fills the whole cell, up to its top-right corner
    assert not white[:, :136].any() and not (img[:62] > 0).any()  # nothing outside the block


def test_span_opacity_multiplies_like_a_group():
    a, b = _cells()
    code = Code("c", content="ab", size=1.0, x=-0.6, y=0.7)
    code.select("hide_b", chars=(1, 2), opacity=0.0)
    img = _frame(code)
    assert (img[a] > 0).any() and not (img[b] > 0).any()
    code.opacity = 0.0  # the block's opacity wins even where a span says 1
    code.select("show_a", chars=(0, 1), opacity=1.0)
    assert not (_frame(code) > 0).any()
