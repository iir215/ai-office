import os
import subprocess
import tempfile

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
LOGO_DIR = os.path.join(STATIC_DIR, "logos")

# The logo is a per-company file, logos/<company_id>.png (transparent PNG), so
# a company without one simply gets unbranded media. It lives in the
# bind-mounted static dir: replacing the file changes branding without a rebuild.
LOGO_WIDTH_RATIO = 0.26


def logo_path(company_id: int) -> str | None:
    path = os.path.join(LOGO_DIR, f"{company_id}.png")
    return path if os.path.exists(path) else None


def _dimensions(path: str) -> tuple[int, int]:
    out = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", path,
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    width, height = out.split("x")
    return int(width), int(height)


def _overlay_filter(width: int, height: int, position: str) -> str:
    logo_w = round(width * LOGO_WIDTH_RATIO)
    margin = round(width * 0.04)
    if position == "top_left":
        # Reels: clear of the top UI bar and still inside the 4:5 profile-grid crop.
        x, y = margin, round(height * 0.15)
    else:
        x, y = f"W-w-{margin}", f"H-h-{margin}"
    return f"[1:v]scale={logo_w}:-1:flags=lanczos[logo];[0:v][logo]overlay=x={x}:y={y}:format=auto"


def overlay_logo_on_image(image_bytes: bytes, company_id: int) -> bytes:
    logo = logo_path(company_id)
    if not logo:
        return image_bytes

    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "in.png")
        dst = os.path.join(tmp, "out.png")
        with open(src, "wb") as f:
            f.write(image_bytes)
        width, height = _dimensions(src)
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", src, "-i", logo,
                "-filter_complex", _overlay_filter(width, height, "bottom_right"),
                "-frames:v", "1", dst,
            ],
            check=True,
            capture_output=True,
        )
        with open(dst, "rb") as f:
            return f.read()


def overlay_logo_on_video(src_path: str, dst_path: str, company_id: int) -> bool:
    """Burns the logo into the video (re-encode) and writes a faststart MP4.
    Returns False, writing nothing, when the company has no logo."""
    logo = logo_path(company_id)
    if not logo:
        return False

    width, height = _dimensions(src_path)
    filt = _overlay_filter(width, height, "top_left") + ",format=yuv420p[v]"
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", src_path, "-i", logo,
            "-filter_complex", filt,
            "-map", "[v]", "-map", "0:a?",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-c:a", "copy", "-movflags", "+faststart",
            dst_path,
        ],
        check=True,
        capture_output=True,
    )
    return True
