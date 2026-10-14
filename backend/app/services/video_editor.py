"""Re-cuts a finished Reel: keeps its first part, appends a new closing scene and
burns animated text over the ending. Pure ffmpeg + Pillow, no network."""
import os
import subprocess
import tempfile
from dataclasses import dataclass, field

from PIL import Image, ImageDraw, ImageFont

from app.services.branding import LOGO_WIDTH_RATIO, logo_path

FONT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "fonts", "Montserrat.ttf")
FPS = 24
XFADE_SECONDS = 0.25
YELLOW = (255, 208, 0)
WHITE = (255, 255, 255)
COLORS = {"white": WHITE, "yellow": YELLOW}
LAYOUTS = ("bottom_stack", "top_headline")


@dataclass
class TextSpec:
    # [{"text": "...", "color": "white" | "yellow"}] — big headline lines.
    headline: list[dict] = field(default_factory=list)
    info_line: str = ""  # small line under the headline, e.g. the address
    chips: list[str] = field(default_factory=list)  # pills: first is filled yellow, others outlined
    # bottom_stack: everything on the lower part (for scenes whose roof/sky is busy);
    # top_headline: headline above the subject, info and chips below.
    layout: str = "bottom_stack"

    def is_empty(self) -> bool:
        return not (self.headline or self.info_line or self.chips)


def _font(size: int, weight: bytes = b"Bold") -> ImageFont.FreeTypeFont:
    font = ImageFont.truetype(FONT_PATH, max(size, 8))
    font.set_variation_by_name(weight)
    return font


def _fit_font(draw: ImageDraw.ImageDraw, text: str, size: int, max_width: float, weight: bytes) -> ImageFont.FreeTypeFont:
    font = _font(size, weight)
    while size > 14 and draw.textlength(text, font=font) > max_width:
        size -= 2
        font = _font(size, weight)
    return font


def _centered(img: Image.Image, y: float, text: str, font: ImageFont.FreeTypeFont, fill, shadow: int) -> None:
    draw = ImageDraw.Draw(img)
    x = (img.width - draw.textlength(text, font=font)) / 2
    for dy, alpha in ((shadow, 110), (max(shadow * 2 // 5, 1), 190)):
        draw.text((x, y + dy), text, font=font, fill=(0, 0, 0, alpha))
    draw.text((x, y), text, font=font, fill=fill)


def _render_layers(spec: TextSpec, width: int, height: int, out_dir: str) -> dict[str, str]:
    """Writes transparent PNG layers (same size as the video) and returns their paths."""
    k = height / 1344
    margin = width * 0.06
    bottom_stack = spec.layout == "bottom_stack"
    layers: dict[str, str] = {}

    grad = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    pixels = grad.load()
    top_a, top_h = (90, 300) if bottom_stack else (175, 520)
    bottom_from = 860 if bottom_stack else 960
    bottom_a, bottom_span = (205, 240) if bottom_stack else (190, 260)
    for y in range(height):
        alpha = 0
        if y < top_h * k:
            alpha = max(alpha, int(top_a * (1 - y / (top_h * k))))
        if y > bottom_from * k:
            alpha = max(alpha, int(bottom_a * min(1, (y - bottom_from * k) / (bottom_span * k))))
        if alpha:
            for x in range(width):
                pixels[x, y] = (0, 0, 0, alpha)
    layers["grad"] = os.path.join(out_dir, "grad.png")
    grad.save(layers["grad"])

    if spec.headline:
        head = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(head)
        pitch = 56 * k
        n = len(spec.headline)
        y0 = (1050 * k - n * pitch) if bottom_stack else 256 * k
        for i, line in enumerate(spec.headline):
            text = line.get("text", "")
            font = _fit_font(draw, text, round(54 * k), width - 2 * margin, b"Bold")
            _centered(head, y0 + i * pitch, text, font, COLORS.get(line.get("color", "white"), WHITE) + (255,), round(5 * k))
        layers["head"] = os.path.join(out_dir, "head.png")
        head.save(layers["head"])

    if spec.info_line or spec.chips:
        info = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(info)
        if spec.info_line:
            font = _fit_font(draw, spec.info_line, round(28 * k), width - 2 * margin, b"Medium")
            _centered(info, (1066 if bottom_stack else 1030) * k, spec.info_line, font, WHITE + (255,), round(4 * k))
        if spec.chips:
            size = round(30 * k)
            pad, gap, h = round(24 * k), round(12 * k), round(58 * k)
            while True:
                font = _font(size, b"SemiBold")
                widths = [draw.textlength(c, font=font) for c in spec.chips]
                total = sum(w + 2 * pad for w in widths) + gap * (len(widths) - 1)
                if total <= width - 2 * margin or size <= 16:
                    break
                size -= 2
            x = (width - total) / 2
            y = (1110 if bottom_stack else 1090) * k
            for i, (chip, w) in enumerate(zip(spec.chips, widths)):
                box = (x, y, x + w + 2 * pad, y + h)
                if i == 0:
                    draw.rounded_rectangle(box, radius=h / 2, fill=YELLOW)
                    draw.text((x + pad, y + h * 0.17), chip, font=font, fill=(15, 15, 15))
                else:
                    draw.rounded_rectangle(box, radius=h / 2, fill=(0, 0, 0, 110), outline=WHITE + (235,), width=3)
                    draw.text((x + pad, y + h * 0.17), chip, font=font, fill=WHITE)
                x += w + 2 * pad + gap
        layers["info"] = os.path.join(out_dir, "info.png")
        info.save(layers["info"])

    return layers


def _probe(path: str) -> dict:
    out = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height:format=duration", "-of", "default=nw=1",
            path,
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    info = dict(line.split("=", 1) for line in out.strip().splitlines())
    return {"width": int(info["width"]), "height": int(info["height"]), "duration": float(info["duration"])}


def probe_duration(path: str) -> float:
    return _probe(path)["duration"]


def recut_with_new_ending(
    source_path: str,
    ending_path: str,
    dst_path: str,
    keep_seconds: float,
    spec: TextSpec,
    company_id: int,
) -> float:
    """Writes source[0:keep_seconds] + crossfade + ending clip (+ logo and text over
    the ending) to dst_path, keeping the source audio. Returns the output duration."""
    src = _probe(source_path)
    end = _probe(ending_path)
    width, height = src["width"], src["height"]
    if not 0.5 <= keep_seconds <= src["duration"]:
        raise ValueError(f"keep_seconds must be between 0.5 and {src['duration']:.1f}")

    keep_frames = round(keep_seconds * FPS)
    keep_len = keep_frames / FPS
    ending_start = keep_len - XFADE_SECONDS
    total = ending_start + end["duration"]

    with tempfile.TemporaryDirectory() as tmp:
        layers = _render_layers(spec, width, height, tmp) if not spec.is_empty() else {}

        inputs = ["-i", source_path, "-i", ending_path]
        index = 2
        layer_idx: dict[str, int] = {}
        for name in ("grad", "head", "info"):
            if name in layers:
                inputs += ["-loop", "1", "-framerate", str(FPS), "-t", f"{total + 0.1:.3f}", "-i", layers[name]]
                layer_idx[name] = index
                index += 1
        logo = logo_path(company_id)
        logo_idx = None
        if logo:
            inputs += ["-i", logo]
            logo_idx = index

        parts = [
            f"[0:v]trim=end_frame={keep_frames},setpts=PTS-STARTPTS,fps={FPS},setsar=1,format=yuv420p[a]",
            f"[1:v]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},"
            f"setpts=PTS-STARTPTS,fps={FPS},setsar=1,format=yuv420p[b0]",
        ]
        if logo_idx is not None:
            logo_w = round(width * LOGO_WIDTH_RATIO)
            parts.append(f"[{logo_idx}:v]scale={logo_w}:-1:flags=lanczos[logo]")
            parts.append(
                f"[b0][logo]overlay=x={round(width * 0.04)}:y={round(height * 0.15)}:format=auto,format=yuv420p[b]"
            )
        else:
            parts.append("[b0]null[b]")
        parts.append(f"[a][b]xfade=transition=fade:duration={XFADE_SECONDS}:offset={ending_start:.3f}[v0]")

        # (layer, fade-in start relative to the ending start, fade length, slide-up pixels)
        timing = {"grad": (0.65, 0.6, 0), "head": (1.05, 0.5, 20), "info": (1.85, 0.5, 20)}
        current = "v0"
        for name in ("grad", "head", "info"):
            if name not in layer_idx:
                continue
            start, dur, slide = timing[name]
            t0 = ending_start + start
            parts.append(f"[{layer_idx[name]}:v]format=rgba,fade=t=in:st={t0:.3f}:d={dur}:alpha=1[{name}]")
            y = f"y='(1-clip((t-{t0:.3f})/{dur},0,1))*{round(slide * height / 1344)}':eval=frame:" if slide else "y=0:"
            nxt = f"v_{name}"
            parts.append(f"[{current}][{name}]overlay=x=0:{y}format=auto[{nxt}]")
            current = nxt
        parts.append(f"[{current}]format=yuv420p[v]")

        subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error", *inputs,
                "-filter_complex", ";".join(parts),
                "-map", "[v]", "-map", "0:a?",
                "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                "-c:a", "copy", "-movflags", "+faststart",
                "-t", f"{total:.3f}", dst_path,
            ],
            check=True,
            capture_output=True,
        )
    return total


def scene_cuts(path: str, threshold: float = 0.35, merge_within: float = 0.6) -> list[float]:
    """Timestamps (seconds) where the picture changes sharply, i.e. where scenes start.
    Dissolves produce several hits in a row, so close ones are merged into the first."""
    proc = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-i", path,
            "-vf", f"select='gt(scene,{threshold})',showinfo",
            "-an", "-f", "null", "-",
        ],
        capture_output=True,
        text=True,
    )
    times = []
    for line in proc.stderr.splitlines():
        if "pts_time:" in line:
            try:
                times.append(float(line.split("pts_time:", 1)[1].split()[0]))
            except ValueError:
                pass
    cuts: list[float] = []
    for t in times:
        if not cuts or t - cuts[-1] > merge_within:
            cuts.append(round(t, 2))
    return cuts


# ---------------------------------------------------------------- brand end card

COLORS["black"] = (0, 0, 0)


def brand_color(company_id: int) -> tuple[int, int, int]:
    """The dominant saturated colour of the company's logo plate (the brand yellow/mustard)."""
    from collections import Counter

    path = logo_path(company_id)
    if not path:
        return YELLOW
    img = Image.open(path).convert("RGBA")
    img.thumbnail((300, 300))
    counts: Counter = Counter()
    for r, g, b, a in img.getdata():
        if a > 220 and max(r, g, b) - min(r, g, b) > 60:
            counts[(r, g, b)] += 1
    return counts.most_common(1)[0][0] if counts else YELLOW


def parse_color(value: str | None, company_id: int) -> tuple[int, int, int]:
    value = (value or "").strip().lower()
    if value in ("", "brand", "mustard", "горчичный"):
        return brand_color(company_id)
    if value in COLORS:
        return COLORS[value]
    value = value.lstrip("#")
    if len(value) == 6:
        try:
            return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
        except ValueError:
            pass
    raise ValueError(f"unknown colour {value!r}: use 'mustard', 'black', 'white' or a #RRGGBB hex")


def _render_card_text(spec: TextSpec, width: int, height: int, text_top: float, out_path: str) -> None:
    k = height / 1344
    margin = width * 0.08
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    y = text_top
    for line in spec.headline:
        text = line.get("text", "")
        font = _fit_font(draw, text, round(50 * k), width - 2 * margin, b"Bold")
        _centered(layer, y, text, font, COLORS.get(line.get("color", "black"), COLORS["black"]) + (255,), 0)
        y += 62 * k
    if spec.info_line:
        font = _fit_font(draw, spec.info_line, round(30 * k), width - 2 * margin, b"SemiBold")
        _centered(layer, y + 18 * k, spec.info_line, font, COLORS["black"] + (255,), 0)
    layer.save(out_path)


def recut_with_end_card(
    source_path: str,
    dst_path: str,
    keep_seconds: float,
    spec: TextSpec,
    company_id: int,
    background: str | None = None,
) -> float:
    """source[0:keep_seconds] + crossfade into a flat-colour brand card: the company
    logo large in the middle, animated text under it. Output keeps the source length
    and audio."""
    src = _probe(source_path)
    width, height = src["width"], src["height"]
    if not 0.5 <= keep_seconds <= src["duration"] - 1:
        raise ValueError(f"keep_seconds must be between 0.5 and {src['duration'] - 1:.1f}")
    logo = logo_path(company_id)
    if not logo:
        raise ValueError("this company has no logo file; a brand card needs one")

    bg = parse_color(background, company_id)
    keep_frames = round(keep_seconds * FPS)
    keep_len = keep_frames / FPS
    card_start = keep_len - XFADE_SECONDS
    card_len = src["duration"] - card_start

    logo_img = Image.open(logo)
    logo_w = round(width * 0.68)
    logo_h = round(logo_w * logo_img.height / logo_img.width)
    logo_y = round(height * 0.40 - logo_h / 2)
    text_top = logo_y + logo_h + round(46 * height / 1344)

    with tempfile.TemporaryDirectory() as tmp:
        text_png = os.path.join(tmp, "card_text.png")
        _render_card_text(spec, width, height, text_top, text_png)

        slide = round(28 * height / 1344)
        t_logo, t_text = 0.35, 0.95
        filt = ";".join([
            f"[0:v]trim=end_frame={keep_frames},setpts=PTS-STARTPTS,fps={FPS},setsar=1,format=yuv420p[a]",
            f"[1:v]format=yuv420p,setsar=1[bg]",
            f"[2:v]scale={logo_w}:-1:flags=lanczos,format=rgba,fade=t=in:st={t_logo}:d=0.55:alpha=1[lg]",
            f"[3:v]format=rgba,fade=t=in:st={t_text}:d=0.5:alpha=1[tx]",
            f"[bg][lg]overlay=x=(W-w)/2:y='{logo_y}+(1-clip((t-{t_logo})/0.55,0,1))*{slide}':eval=frame:format=auto[c1]",
            f"[c1][tx]overlay=x=0:y='(1-clip((t-{t_text})/0.5,0,1))*{slide}':eval=frame:format=auto,fps={FPS},format=yuv420p[c]",
            f"[a][c]xfade=transition=fade:duration={XFADE_SECONDS}:offset={card_start:.3f},format=yuv420p[v]",
        ])
        hex_bg = "0x%02x%02x%02x" % bg
        subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error",
                "-i", source_path,
                "-f", "lavfi", "-i", f"color=c={hex_bg}:s={width}x{height}:r={FPS}:d={card_len + 0.2:.3f}",
                "-loop", "1", "-framerate", str(FPS), "-t", f"{card_len + 0.2:.3f}", "-i", logo,
                "-loop", "1", "-framerate", str(FPS), "-t", f"{card_len + 0.2:.3f}", "-i", text_png,
                "-filter_complex", filt,
                "-map", "[v]", "-map", "0:a?",
                "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                "-c:a", "copy", "-movflags", "+faststart",
                "-t", f"{src['duration']:.3f}", dst_path,
            ],
            check=True,
            capture_output=True,
        )
    return src["duration"]
