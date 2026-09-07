import shutil
import struct

import numpy as np
import pytest

from buttery import Circle, Line, Rect, Scene, Text, tween
from buttery import tools
from buttery.render import Rasterizer, encode_png


def png_size(data: bytes) -> tuple[int, int]:
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", data[16:24])


def small_scene(**kw):
    dot = Circle("dot", r=0.5, fill="red", x=tween(-3, 3, at=0, dur=0.5))
    return Scene(duration=0.2, fps=10, size=(320, 180), objects=[dot], **kw)


def test_preview_size_and_bytes():
    png = small_scene().preview(0.0, scale=0.5)
    assert png_size(png) == (160, 90)


def test_pixels_land_where_expected():
    # red dot at world origin on a black background, no motion
    scene = Scene(duration=1, size=(320, 180), background="black", objects=[Circle("d", r=0.5, fill="red")])
    arr = Rasterizer(scene.compile(), 320, 180).frame(0, motion_blur=False)
    assert arr.shape == (180, 320, 4)
    assert tuple(arr[90, 160, :3]) == (255, 0, 0)
    assert tuple(arr[5, 5, :3]) == (0, 0, 0)
    # y is up: a rect at y=+1.5 lands in the top half
    scene = Scene(duration=1, size=(320, 180), background="black", objects=[Rect("r", y=1.5, w=1, h=0.5, fill="white")])
    arr = Rasterizer(scene.compile(), 320, 180).frame(0, motion_blur=False)
    assert arr[:90, :, 0].max() == 255 and arr[90:, :, 0].max() == 0


def test_motion_blur_smears_moving_object():
    scene = small_scene()
    ras = Rasterizer(scene.compile(), 320, 180)
    sharp = ras.frame(0.1, motion_blur=False)
    blurred = ras.frame(0.1, motion_blur=True, samples=8)
    red_sharp = (sharp[..., 0] > 128).sum()
    red_blur = (blurred[..., 0] > 32).sum()
    assert red_blur > red_sharp  # blur covers more ground
    assert 0 < (blurred[..., 0] == 255).sum() < (sharp[..., 0] == 255).sum()  # fewer fully saturated pixels


def test_static_scene_is_unaffected_by_blur():
    scene = Scene(duration=1, size=(160, 90), objects=[Circle("d", r=0.5, fill="red"), Text("t", content="Hi", y=-1)])
    ras = Rasterizer(scene.compile(), 160, 90)
    a = ras.frame(0.3, motion_blur=False)
    b = ras.frame(0.3, motion_blur=True, samples=4)
    assert np.array_equal(a, b)


def test_render_png_sequence(tmp_path):
    scene = small_scene()
    result = scene.render(tmp_path / "frames", workers=1, samples=2)
    assert result.frames == 2
    files = sorted(p.name for p in (tmp_path / "frames").iterdir())
    assert files == ["frame_00000.png", "frame_00001.png"]
    assert png_size((tmp_path / "frames" / "frame_00000.png").read_bytes()) == (320, 180)


def test_render_parallel(tmp_path):
    scene = Scene(duration=0.5, fps=12, size=(160, 90), objects=[Circle("d", x="t")])
    result = scene.render(tmp_path / "frames", workers=2, samples=2)
    assert result.frames == 6 and len(list((tmp_path / "frames").iterdir())) == 6


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_render_mp4(tmp_path):
    scene = Scene(duration=0.5, fps=12, size=(160, 90), objects=[Circle("d", x="t")])
    result = scene.render(tmp_path / "out.mp4", workers=1, samples=2)
    data = (tmp_path / "out.mp4").read_bytes()
    assert result.frames == 6 and len(data) > 500 and b"ftyp" in data[:32]


def test_encode_png_roundtrip_shape():
    arr = np.zeros((4, 6, 4), dtype=np.uint8)
    assert png_size(encode_png(arr)) == (6, 4)


def test_tools_surface(tmp_path):
    js = small_scene().to_json()
    assert tools.validate(js)["ok"]
    st = tools.state(js, 0.25)
    assert st["ok"] and st["objects"][0]["x"] == pytest.approx(0.0)
    pv = tools.preview(js, 0.1, 0.5, path=str(tmp_path / "p.png"))
    assert pv["ok"] and (pv["width"], pv["height"]) == (160, 90) and (tmp_path / "p.png").exists()
    rr = tools.render(js, str(tmp_path / "seq"), workers=1, samples=1)
    assert rr["ok"] and rr["frames"] == 2
    bad = tools.state('{"duration": 1, "objects": [{"id": "a", "type": "circle", "x": "zz.x"}]}', 0)
    assert bad == {"ok": False, "errors": [{"path": "objects[0].x", "message": "reference 'zz.x': no object with id 'zz'", "object": "a", "property": "x"}]}
    div = tools.state('{"duration": 1, "objects": [{"id": "a", "type": "circle", "x": "1/t"}]}', 0)
    assert div["errors"][0]["t"] == 0.0 and div["errors"][0]["object"] == "a"


def test_cli_validate_and_state(tmp_path, capsys):
    from buttery.cli import main

    p = tmp_path / "s.json"
    p.write_text(small_scene().to_json())
    assert main(["validate", str(p)]) == 0
    assert main(["state", str(p), "--t", "0.1"]) == 0
    p.write_text('{"duration": 1, "objects": [{"id": "a", "type": "circle", "x": "b.x"}]}')
    assert main(["validate", str(p)]) == 1
    assert '"ok": false' in capsys.readouterr().out


def _ink_bbox(frame):
    """Rows and columns that contain any non-background pixel."""
    ink = frame[..., :3].max(axis=2) > 40
    rows = np.where(ink.any(axis=1))[0]
    cols = np.where(ink.any(axis=0))[0]
    return rows.min(), rows.max(), cols.min(), cols.max()


def test_wrap_lines_breaks_at_words_and_keeps_newlines():
    from buttery.render import wrap_lines

    measure = len  # one unit per character
    assert wrap_lines("one two three four", measure, 9) == ["one two", "three", "four"]
    assert wrap_lines("short\nalso short", measure, 50) == ["short", "also short"]
    assert wrap_lines("supercalifragilistic word", measure, 5) == ["supercalifragilistic", "word"]
    assert wrap_lines("no wrap", measure, None) == ["no wrap"]


def test_text_max_width_wraps_into_a_taller_narrower_block():
    long = "the quick brown fox jumps over the lazy dog again and again"
    wide = Scene(duration=1, size=(320, 180), view_width=8, objects=[Text("t", content=long, size=0.3)])
    wrapped = Scene(duration=1, size=(320, 180), view_width=8,
                    objects=[Text("t", content=long, size=0.3, max_width=3.0)])
    a = _ink_bbox(Rasterizer(wide.compile(), 320, 180).frame(0.0, motion_blur=False))
    b = _ink_bbox(Rasterizer(wrapped.compile(), 320, 180).frame(0.0, motion_blur=False))
    assert (b[3] - b[2]) < (a[3] - a[2])          # narrower
    assert (b[1] - b[0]) > 2 * (a[1] - a[0])      # several lines tall
    assert b[3] - b[2] <= 3.0 * 40 + 2            # inside max_width (40 px per unit), antialias slack
    assert abs((b[0] + b[1]) / 2 - 90) < 6        # block stays centered on y=0
