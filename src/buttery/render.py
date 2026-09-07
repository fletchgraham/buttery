"""Rasterize resolved states with skia. Motion blur = average of sub-frames across the shutter."""

from __future__ import annotations

import math
import os
import shutil
import subprocess
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

import numpy as np
import skia

from .color import parse_color
from .errors import RenderError

if TYPE_CHECKING:
    from .evaluate import CompiledScene
    from .scene import Scene

VIDEO_SUFFIXES = {".mp4", ".mov"}


@dataclass
class RenderResult:
    path: str
    frames: int
    duration: float
    fps: int
    width: int
    height: int
    seconds: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Rasterizer:
    """Draws `CompiledScene.state(t)` onto a skia surface of a given pixel size."""

    def __init__(self, compiled: "CompiledScene", width: int, height: int) -> None:
        self.compiled = compiled
        self.scene = compiled.scene
        self.width = width
        self.height = height
        self.px = width / self.scene.view_width
        self.surface = skia.Surface(width, height)
        self.canvas = self.surface.getCanvas()
        self.bg = _skcolor(parse_color(self.scene.background))
        self._typefaces: dict[str | None, skia.Typeface] = {}

    # ------------------------------------------------------------------ public

    def draw(self, t: float) -> None:
        state = self.compiled.state(t)
        c = self.canvas
        c.clear(self.bg)
        c.save()
        c.translate(self.width / 2.0, self.height / 2.0)
        c.scale(self.px, -self.px)  # world units, y up
        for obj in state["objects"]:
            self._draw_object(obj, 1.0)
        c.restore()

    def array(self, t: float) -> np.ndarray:
        self.draw(t)
        return self.surface.toarray()

    def frame(self, t: float, motion_blur: bool = True, samples: int = 8, shutter: float = 0.5) -> np.ndarray:
        """RGBA uint8 (h, w, 4). With motion blur, averages `samples` sub-frames over the shutter."""
        if not motion_blur or samples <= 1:
            return self.array(t).copy()
        span = shutter / self.scene.fps
        acc = np.zeros((self.height, self.width, 4), dtype=np.float32)
        for i in range(samples):
            st = t + span * ((i + 0.5) / samples - 0.5)
            acc += self.array(st)
        acc /= samples
        return np.rint(acc).astype(np.uint8)

    def png(self, t: float, **kw: Any) -> bytes:
        return encode_png(self.frame(t, **kw))

    # ------------------------------------------------------------------ drawing

    def _draw_object(self, o: dict[str, Any], alpha: float) -> None:
        a = alpha * _clamp01(o["opacity"])
        if a <= 0.0:
            return
        kind = o["type"]
        c = self.canvas
        if kind == "circle":
            self._fill_stroke(o, a, lambda p: c.drawCircle(o["x"], o["y"], max(o["r"], 0.0), p))
        elif kind == "rect":
            w, h = max(o["w"], 0.0), max(o["h"], 0.0)
            rr = max(o["corner_radius"], 0.0)
            rect = skia.Rect.MakeXYWH(-w / 2.0, -h / 2.0, w, h)
            c.save()
            c.translate(o["x"], o["y"])
            c.rotate(o["rotation"])
            self._fill_stroke(o, a, lambda p: c.drawRoundRect(rect, rr, rr, p))
            c.restore()
        elif kind == "line":
            if o["stroke"] is not None and o["stroke_width"] > 0:
                p = self._paint(o["stroke"], a, stroke_width=o["stroke_width"])
                c.drawLine(o["x1"], o["y1"], o["x2"], o["y2"], p)
        elif kind == "text":
            self._draw_text(o, a)
        elif kind == "group":
            c.save()
            c.translate(o["x"], o["y"])
            c.rotate(o["rotation"])
            s = o["scale"]
            c.scale(s, s)
            if a < 1.0:
                c.saveLayerAlpha(None, int(round(a * 255)))
                for child in o["children"]:
                    self._draw_object(child, 1.0)
                c.restore()
            else:
                for child in o["children"]:
                    self._draw_object(child, 1.0)
            c.restore()

    def _fill_stroke(self, o: dict[str, Any], a: float, draw: Callable[[skia.Paint], None]) -> None:
        if o["fill"] is not None:
            draw(self._paint(o["fill"], a))
        if o["stroke"] is not None and o["stroke_width"] > 0:
            draw(self._paint(o["stroke"], a, stroke_width=o["stroke_width"]))

    def _draw_text(self, o: dict[str, Any], a: float) -> None:
        content = o["content"]
        if not content or o["fill"] is None or o["size"] <= 0:
            return
        c = self.canvas
        size_px = o["size"] * self.px
        font = skia.Font(self._typeface(o["font"]), size_px)
        font.setSubpixel(True)
        font.setEdging(skia.Font.Edging.kSubpixelAntiAlias)
        width = font.measureText(content)
        metrics = font.getMetrics()
        cap = metrics.fCapHeight if metrics.fCapHeight > 0 else -(metrics.fAscent + metrics.fDescent)
        align = o["align"]
        dx = -width / 2.0 if align == "center" else (-width if align == "right" else 0.0)
        c.save()
        c.translate(o["x"], o["y"])
        c.scale(1.0 / self.px, -1.0 / self.px)  # back to pixel space, y down, for crisp glyphs
        c.drawString(content, dx, cap / 2.0, font, self._paint(o["fill"], a))
        c.restore()

    def _paint(self, color: str, alpha: float, stroke_width: float | None = None) -> skia.Paint:
        r, g, b, ca = parse_color(color)
        p = skia.Paint(AntiAlias=True)
        p.setColor4f(skia.Color4f(r, g, b, ca * alpha))
        if stroke_width is not None:
            p.setStyle(skia.Paint.kStroke_Style)
            p.setStrokeWidth(stroke_width)
            p.setStrokeCap(skia.Paint.kRound_Cap)
            p.setStrokeJoin(skia.Paint.kRound_Join)
        return p

    def _typeface(self, name: str | None) -> skia.Typeface:
        if name not in self._typefaces:
            self._typefaces[name] = _match_typeface(name)
        return self._typefaces[name]


# ---------------------------------------------------------------------- helpers

DEFAULT_FONTS = ("Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans", "Liberation Sans")
_font_mgr: skia.FontMgr | None = None


def _match_typeface(name: str | None) -> skia.Typeface:
    """Resolve a family name; fall back through DEFAULT_FONTS, then whatever the system offers."""
    global _font_mgr
    if _font_mgr is None:
        _font_mgr = skia.FontMgr()
    for candidate in ((name,) if name else ()) + DEFAULT_FONTS:
        tf = _font_mgr.matchFamilyStyle(candidate, skia.FontStyle())
        if tf is not None:
            return tf
    return _font_mgr.legacyMakeTypeface("", skia.FontStyle())


def _clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


def _skcolor(rgba: tuple[float, float, float, float]) -> int:
    r, g, b, a = rgba
    return skia.ColorSetARGB(round(a * 255), round(r * 255), round(g * 255), round(b * 255))


def encode_png(rgba: np.ndarray) -> bytes:
    img = skia.Image.fromarray(np.ascontiguousarray(rgba), skia.ColorType.kRGBA_8888_ColorType)
    data = img.encodeToData(skia.EncodedImageFormat.kPNG, 100)
    if data is None:
        raise RenderError("PNG encoding failed")
    return bytes(data)


def scaled_size(scene: "Scene", scale: float) -> tuple[int, int]:
    w, h = scene.size
    return max(1, round(w * scale)), max(1, round(h * scale))


def preview(scene: "Scene", t: float = 0.0, scale: float = 0.25, path: str | Path | None = None) -> bytes:
    compiled = scene.compile()
    w, h = scaled_size(scene, scale)
    png = Rasterizer(compiled, w, h).png(t, motion_blur=False)
    if path is not None:
        Path(path).write_bytes(png)
    return png


# ---------------------------------------------------------------------- render (parallel)

_worker: Rasterizer | None = None
_worker_opts: dict[str, Any] = {}


def _init_worker(scene_data: dict[str, Any], opts: dict[str, Any]) -> None:
    global _worker, _worker_opts
    from .scene import Scene

    scene = Scene.model_validate(scene_data)
    _worker = Rasterizer(scene.compile(), *scene.size)
    _worker_opts = opts


def _render_chunk(args: tuple[str, list[int]]) -> int:
    out_dir, frames = args
    assert _worker is not None
    return _write_frames(_worker, _worker_opts, out_dir, frames)


def _write_frames(ras: Rasterizer, opts: dict[str, Any], out_dir: str, frames: list[int]) -> int:
    fps = ras.scene.fps
    for i in frames:
        png = ras.png(i / fps, **opts)
        Path(out_dir, f"frame_{i:05d}.png").write_bytes(png)
    return len(frames)


def render(
    scene: "Scene",
    path: str | Path,
    *,
    motion_blur: bool = True,
    samples: int = 8,
    shutter: float = 0.5,
    workers: int | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> RenderResult:
    """Render the whole scene.

    `path` ending in .mp4/.mov -> H.264 video via ffmpeg. Anything else -> directory of PNG frames.
    `shutter` is the fraction of the frame interval the virtual shutter stays open (0.5 = 180 degrees).
    Frames are independent and are rendered in parallel across `workers` processes (default: all cores).
    """
    compiled = scene.compile()  # validates
    out = Path(path)
    n = scene.frame_count
    is_video = out.suffix.lower() in VIDEO_SUFFIXES
    if is_video and shutil.which("ffmpeg") is None:
        raise RenderError("ffmpeg not found on PATH; install it or render to a PNG sequence directory instead")
    opts = {"motion_blur": motion_blur, "samples": max(1, int(samples)), "shutter": shutter}
    started = time.perf_counter()

    tmp: tempfile.TemporaryDirectory[str] | None = None
    if is_video:
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = tempfile.TemporaryDirectory(prefix="buttery_")
        frames_dir = Path(tmp.name)
    else:
        frames_dir = out
        frames_dir.mkdir(parents=True, exist_ok=True)

    try:
        workers = workers or os.cpu_count() or 1
        workers = max(1, min(workers, n))
        if workers == 1:
            ras = Rasterizer(compiled, *scene.size)
            done = 0
            for i in range(n):
                _write_frames(ras, opts, str(frames_dir), [i])
                done += 1
                if on_progress:
                    on_progress(done, n)
        else:
            chunk = max(1, math.ceil(n / (workers * 4)))
            chunks = [(str(frames_dir), list(range(s, min(s + chunk, n)))) for s in range(0, n, chunk)]
            scene_data = scene.model_dump(mode="json")
            done = 0
            with ProcessPoolExecutor(max_workers=workers, initializer=_init_worker, initargs=(scene_data, opts)) as pool:
                for count in pool.map(_render_chunk, chunks):
                    done += count
                    if on_progress:
                        on_progress(done, n)
        if is_video:
            _encode_video(frames_dir, out, scene.fps)
    finally:
        if tmp is not None:
            tmp.cleanup()

    return RenderResult(
        path=str(out), frames=n, duration=n / scene.fps, fps=scene.fps,
        width=scene.size[0], height=scene.size[1], seconds=round(time.perf_counter() - started, 3),
    )


def _encode_video(frames_dir: Path, out: Path, fps: int) -> None:
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-framerate", str(fps), "-i", str(frames_dir / "frame_%05d.png"),
        "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = proc.stderr.strip().splitlines()[-5:]
        raise RenderError("ffmpeg failed: " + " | ".join(tail))


__all__ = ["Rasterizer", "RenderResult", "encode_png", "preview", "render"]
