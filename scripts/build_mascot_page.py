"""Builds backend/app/static/shop/mascot.html as ONE self-contained file (images inlined as data URIs).

The server answers fast locally but the public path is slow (1-2 s per request, ~50 KB/s for big
files), so a page with a dozen separate images and a 650 KB logo does not finish loading on a phone.
One small file does. Template: scripts/mascot_template.html (uses relative image paths).

    python scripts/build_mascot_page.py
"""
import base64
import io
import os
import re

from PIL import Image

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SHOP = os.path.join(ROOT, "backend", "app", "static", "shop")
TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mascot_template.html")
OUT = os.path.join(SHOP, "mascot.html")


def b64(data: bytes, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(data).decode()


def jpeg(path: str, width: int, quality: int) -> str:
    im = Image.open(path).convert("RGB")
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=quality, optimize=True)
    return b64(buf.getvalue(), "image/jpeg")


def png_file(path: str) -> str:
    with open(path, "rb") as f:
        return b64(f.read(), "image/png")


def logo() -> str:
    im = Image.open(os.path.join(ROOT, "backend", "app", "static", "logos", "2.png")).convert("RGBA")
    im = im.resize((520, round(im.height * 520 / im.width)), Image.NEAREST)   # pixel art: keep edges sharp
    buf = io.BytesIO()
    im.quantize(colors=16, method=Image.FASTOCTREE).save(buf, "PNG", optimize=True)
    return b64(buf.getvalue(), "image/png")


def main() -> None:
    src = open(TEMPLATE, encoding="utf-8").read()

    # JS: image references -> P('...') lookups
    src = re.sub(r"M \+ '([A-Za-z0-9_]+\.jpg)", r"P('mascot/\1') + '", src)
    src = re.sub(r"S \+ (\w+) \+ '\.png", r"P('sprites/' + \1 + '.png') + '", src)
    src = re.sub(r"S \+ '([A-Za-z0-9_]+\.png)", r"P('sprites/\1') + '", src)
    src = src.replace('src="/ui/logos/2.png"', "src=\"' + P('logo') + '\"")

    assets = {"logo": logo()}
    wanted = set(re.findall(r"P\('(mascot/[A-Za-z0-9_]+\.jpg|sprites/[A-Za-z0-9_]+\.png)'\)", src))
    wanted |= {f"sprites/{n}.png" for n in ["burger_cheese", "burger_double", "fries_m", "shake_choco", "hotdog_classic", "drink_cola", "nuggets", "juice_orange", "flame"]}
    for key in sorted(wanted):
        path = os.path.join(SHOP, key)
        if key.startswith("mascot/"):
            width = 330 if "hero" in key else 300
            assets[key] = jpeg(path, width, 80)
        else:
            assets[key] = png_file(path)

    # CSS band
    src = src.replace("url(sprites/band.png)", "url(" + png_file(os.path.join(SHOP, "sprites", "band.png")) + ")")

    import json
    js_assets = "var ASSETS = " + json.dumps(assets) + ";\nfunction P(k) { return ASSETS[k]; }\n"
    src = src.replace("(function () {\n  var M = ", js_assets + "(function () {\n  var M = ", 1)
    assert "ASSETS" in src, "template anchor not found"

    leftovers = re.findall(r'(?:src|href)="(?:sprites/|mascot/|/ui/)[^"]*"', src)
    assert not leftovers, leftovers[:5]
    open(OUT, "w", encoding="utf-8").write(src)
    print(f"{os.path.normpath(OUT)}: {len(src) // 1024} KB, {len(assets)} inlined images")


if __name__ == "__main__":
    main()
