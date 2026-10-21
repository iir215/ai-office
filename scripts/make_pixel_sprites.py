"""Draws the 24x24 pixel-art sprites used by the ordering Mini App (one PNG per menu item
and a flame for the "by Baursak" mark) into backend/app/static/shop/sprites/.

    python scripts/make_pixel_sprites.py            # writes the sprites + a preview sheet

The art is generated from code (shapes + an automatic dark outline), so changing a colour or
a shape and re-running is enough; the Mini App scales the PNGs with image-rendering: pixelated.
"""
import math
import os
import sys

from PIL import Image

OUT = os.path.join(os.path.dirname(__file__), "..", "backend", "app", "static", "shop", "sprites")
N = 24
INK = (20, 20, 20, 255)


def C(r, g, b):
    return (r, g, b, 255)


BUN, BUN_D, SESAME = C(238, 160, 50), C(204, 122, 32), C(255, 240, 200)
PATTY, PATTY_L = C(104, 58, 30), C(140, 82, 42)
CHEESE, CHEESE_D = C(252, 201, 4), C(235, 170, 0)
LETTUCE, LETTUCE_L = C(70, 160, 60), C(130, 205, 85)
TOMATO, ONION = C(222, 52, 42), C(240, 225, 245)
CHICKEN, CHICKEN_D = C(226, 150, 52), C(184, 104, 30)
RED, RED_D = C(220, 44, 40), C(168, 28, 30)
WHITE, GREY = C(250, 248, 240), C(196, 196, 190)
YELLOW, ORANGE = C(252, 201, 4), C(242, 106, 27)
GREEN, GREEN_D = C(31, 77, 58), C(24, 56, 42)
BROWN, BROWN_D = C(120, 72, 34), C(80, 46, 20)
BLUE, BLUE_D, BLUE_L = C(40, 100, 200), C(24, 64, 140), C(150, 200, 250)
CREAM, PINK, CHOCO = C(248, 232, 190), C(244, 150, 170), C(96, 56, 36)


class Sprite:
    def __init__(self, w=N, h=N):
        self.w, self.h = w, h
        self.px = {}

    def set(self, x, y, color):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[(x, y)] = color

    def rect(self, x0, y0, x1, y1, color):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                self.set(x, y, color)

    def ellipse(self, cx, cy, rx, ry, color):
        for y in range(int(cy - ry - 1), int(cy + ry + 2)):
            for x in range(int(cx - rx - 1), int(cx + rx + 2)):
                if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0:
                    self.set(x, y, color)

    def line(self, x0, y0, x1, y1, color):
        steps = max(abs(x1 - x0), abs(y1 - y0)) or 1
        for i in range(steps + 1):
            self.set(round(x0 + (x1 - x0) * i / steps), round(y0 + (y1 - y0) * i / steps), color)

    def trapezoid(self, y0, y1, top_half, bottom_half, cx, color):
        for y in range(y0, y1 + 1):
            t = (y - y0) / max(y1 - y0, 1)
            half = top_half + (bottom_half - top_half) * t
            for x in range(math.ceil(cx - half), math.floor(cx + half) + 1):
                self.set(x, y, color)

    def outline(self):
        out = dict(self.px)
        for (x, y) in list(self.px):
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                p = (x + dx, y + dy)
                if p not in self.px and 0 <= p[0] < self.w and 0 <= p[1] < self.h:
                    out[p] = INK
        self.px = out
        return self

    def image(self):
        img = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        for (x, y), c in self.px.items():
            img.putpixel((x, y), c)
        return img


# ----------------------------------------------------------------- food families

def burger(layers):
    s = Sprite()
    heights = {"patty": 3, "chicken": 3, "cheese": 2, "lettuce": 2, "tomato": 2, "onion": 1}
    patty_h = 3
    top = 20 - sum(heights[l] for l in layers) - 3 - 7
    if top < 1:
        patty_h, top = 2, 20 - sum((2 if l in ("patty", "chicken") else heights[l]) for l in layers) - 3 - 7
    top = max(top, 1)
    s.ellipse(12, top + 6, 9, 6.4, BUN)               # dome
    s.rect(2, top + 6, 21, top + 7, BUN)
    for dx, dy in ((7, 2), (11, 1), (15, 2), (9, 4), (13, 4), (17, 4)):
        s.set(dx, top + dy + 1, SESAME)
    y = top + 8
    for l in layers:
        if l == "lettuce":
            s.rect(2, y, 21, y + 1, LETTUCE)
            for x in range(2, 22, 3):
                s.set(x, y + 2, LETTUCE_L)
            s.set(1, y + 1, LETTUCE)
            s.set(22, y + 1, LETTUCE)
            y += 2
        elif l == "tomato":
            s.rect(3, y, 20, y + 1, TOMATO)
            y += 2
        elif l == "onion":
            s.rect(4, y, 19, y, ONION)
            y += 1
        elif l == "cheese":
            s.rect(2, y, 21, y, CHEESE)
            s.rect(3, y + 1, 20, y + 1, CHEESE_D)
            s.rect(5, y + 2, 6, y + 2, CHEESE)
            s.rect(15, y + 2, 17, y + 2, CHEESE)
            y += 2
        elif l == "patty":
            s.rect(2, y, 21, y + patty_h - 1, PATTY)
            for x in range(4, 21, 4):
                s.set(x, y + patty_h // 2, PATTY_L)
            y += patty_h
        elif l == "chicken":
            s.rect(2, y, 21, y + patty_h - 1, CHICKEN)
            for x in range(3, 21, 3):
                s.set(x, y, CHICKEN_D)
            y += patty_h
    s.rect(3, y, 20, y + 2, BUN_D)
    s.rect(4, y + 3, 19, y + 3, BUN_D)
    return s.outline()


def hotdog(kind):
    s = Sprite()
    SAUSAGE, SAUSAGE_L, SAUSAGE_D = C(214, 104, 80), C(238, 150, 120), C(168, 62, 46)
    # sausage resting in the bun, sticking out of both ends
    s.rect(1, 9, 22, 13, SAUSAGE)
    s.rect(2, 8, 21, 8, SAUSAGE)
    s.rect(2, 10, 21, 10, SAUSAGE_L)
    s.rect(2, 13, 21, 13, SAUSAGE_D)
    # bun: back piece, then front piece over the lower sausage
    s.rect(3, 12, 20, 14, BUN_D)
    s.rect(2, 14, 21, 19, BUN)
    s.rect(3, 20, 20, 20, BUN_D)
    s.rect(3, 15, 20, 15, C(255, 190, 90))
    s.rect(4, 18, 19, 19, BUN_D) if False else None
    sauces = {"classic": [RED, YELLOW], "cheese": [CHEESE, CHEESE_D], "hunter": [BROWN_D, BROWN], "spicy": [RED, RED_D]}[kind]
    for i, x in enumerate(range(2, 22, 2)):
        c = sauces[i % 2]
        y = 6 if i % 2 == 0 else 7
        s.rect(x, y, x + 1, y + 1, c)
    if kind == "hunter":
        for x in (4, 9, 14, 19):
            s.set(x, 5, ONION)
    if kind == "spicy":
        for x in (5, 11, 17):
            s.rect(x, 5, x + 1, 5, LETTUCE_L)
    return s.outline()


def fries(size):
    s = Sprite()
    heights = {"s": [5, 6, 5, 6], "m": [8, 10, 9, 11, 9], "l": [10, 13, 12, 14, 12, 13]}[size]
    width = {"s": 12, "m": 14, "l": 18}[size]
    x0 = 12 - width // 2
    base = 14
    for i, h in enumerate(heights):
        x = x0 + 1 + i * (width - 2) // len(heights)
        w = max((width - 2) // len(heights), 2)
        s.rect(x, base - h, x + w - 1, base, YELLOW if i % 2 == 0 else C(238, 180, 20))
        s.set(x, base - h, C(255, 232, 120))
    top_w = width // 2 + 1
    s.trapezoid(base, 21, top_w, top_w - 2, 12, RED)
    s.rect(12 - top_w + 2, base + 3, 12 + top_w - 2, base + 4, WHITE)
    s.rect(12 - top_w + 2, base + 5, 12 + top_w - 2, base + 5, YELLOW)
    return s.outline()


def nuggets():
    s = Sprite()
    for cx, cy, rx, ry in ((7, 11, 4.6, 3.6), (16, 9, 4.2, 3.4), (11, 16, 5, 3.6), (18, 17, 3.6, 3)):
        s.ellipse(cx, cy, rx, ry, CHICKEN)
        s.ellipse(cx - 1, cy - 1, rx - 1.6, ry - 1.5, C(240, 176, 70))
        s.set(int(cx + 1), int(cy + 1), CHICKEN_D)
    return s.outline()


def wings():
    s = Sprite()
    for ox, oy in ((0, 0), (5, 5)):
        s.ellipse(8 + ox, 9 + oy, 4.6, 4.2, CHICKEN)
        s.ellipse(7 + ox, 8 + oy, 3, 2.6, C(240, 176, 70))
        s.line(11 + ox, 12 + oy, 14 + ox, 15 + oy, WHITE)
        s.line(11 + ox, 13 + oy, 14 + ox, 16 + oy, WHITE)
        s.rect(14 + ox, 15 + oy, 15 + ox, 16 + oy, WHITE)
        s.set(16 + ox, 16 + oy, WHITE)
        s.set(14 + ox, 17 + oy, WHITE)
    return s.outline()


def sauce(color, dark, extra=None):
    s = Sprite()
    s.trapezoid(10, 20, 8, 6, 12, WHITE)
    s.rect(4, 8, 19, 10, WHITE)
    s.rect(5, 6, 18, 8, color)
    s.rect(7, 4, 16, 6, color)
    s.rect(9, 3, 14, 4, dark)
    s.rect(7, 13, 16, 16, color)                        # label band
    s.rect(7, 16, 16, 16, dark)
    if extra == "garlic":
        for x, y in ((8, 14), (11, 15), (14, 14)):
            s.set(x, y, LETTUCE_L)
    if extra == "hot":
        s.rect(10, 18, 13, 19, RED)
    return s.outline()


def shake(fill, dark):
    s = Sprite()
    s.trapezoid(9, 21, 7, 5, 12, fill)
    s.rect(4, 8, 19, 9, WHITE)
    s.rect(8, 12, 15, 17, dark)
    s.ellipse(12, 6, 6, 3, WHITE)                      # cream
    s.ellipse(12, 4, 4, 2.4, WHITE)
    s.rect(11, 1, 13, 2, RED)                          # cherry
    s.line(17, 0, 14, 8, RED)
    s.line(18, 0, 15, 8, WHITE)
    return s.outline()


def can(color, dark, light):
    s = Sprite()
    s.rect(7, 4, 16, 21, color)
    s.rect(6, 3, 17, 4, GREY)
    s.rect(6, 21, 17, 21, GREY)
    s.rect(7, 5, 8, 20, light)
    s.rect(15, 5, 16, 20, dark)
    s.ellipse(12, 12, 3.2, 3.2, WHITE)
    s.rect(9, 12, 14, 12, color)
    return s.outline()


def bottle(body, cap, label):
    s = Sprite()
    s.rect(10, 1, 13, 3, cap)
    s.rect(10, 4, 13, 6, body)
    s.trapezoid(7, 10, 2, 5, 12, body)
    s.rect(7, 11, 16, 21, body)
    s.rect(7, 13, 16, 17, label)
    s.set(8, 12, WHITE)
    s.set(8, 19, WHITE)
    return s.outline()


def juice(liquid, fruit):
    s = Sprite()
    s.trapezoid(7, 21, 7, 5, 12, C(235, 245, 250))
    s.trapezoid(10, 21, 6, 4, 12, liquid)
    s.rect(5, 6, 18, 7, C(235, 245, 250))
    s.line(16, 0, 13, 9, RED)
    s.line(17, 0, 14, 9, WHITE)
    if fruit == "slice":
        s.ellipse(18, 7, 3.4, 3.4, liquid)
        s.ellipse(18, 7, 2, 2, C(255, 240, 200))
    elif fruit == "seeds":
        s.ellipse(18, 7, 3, 3, RED_D)
        s.set(17, 6, RED), s.set(19, 7, RED), s.set(18, 8, RED)
    elif fruit == "apple":
        s.ellipse(18, 7, 3, 3, LETTUCE_L)
        s.set(18, 3, BROWN_D)
    elif fruit == "carrot":
        s.line(17, 4, 21, 9, ORANGE), s.line(18, 4, 22, 9, ORANGE)
        s.rect(16, 3, 17, 4, LETTUCE)
    elif fruit == "both":
        s.ellipse(19, 6, 2.4, 2.4, LETTUCE_L)
        s.line(2, 5, 6, 9, ORANGE), s.line(3, 5, 7, 9, ORANGE)
    return s.outline()


def tea_glass(liquid):
    s = Sprite()
    s.trapezoid(5, 12, 6, 3, 12, C(235, 245, 250))
    s.trapezoid(12, 18, 3, 6, 12, C(235, 245, 250))
    s.trapezoid(7, 12, 5, 2, 12, liquid)
    s.trapezoid(12, 17, 2, 5, 12, liquid)
    s.rect(5, 19, 18, 20, WHITE)
    s.rect(6, 21, 17, 21, GREY)
    s.line(16, 1, 14, 6, GREY)
    return s.outline()


def teapot():
    s = Sprite()
    s.ellipse(11, 14, 7, 6, C(200, 205, 210))
    s.rect(7, 7, 15, 9, C(200, 205, 210))
    s.rect(9, 4, 13, 6, C(160, 165, 170))
    s.rect(11, 2, 11, 3, C(160, 165, 170))
    s.line(18, 11, 22, 7, C(200, 205, 210)), s.line(18, 12, 22, 8, C(200, 205, 210))
    s.line(4, 10, 2, 14, C(160, 165, 170)), s.line(2, 14, 4, 18, C(160, 165, 170))
    s.rect(7, 12, 14, 13, C(230, 235, 240))
    s.rect(7, 19, 15, 20, C(160, 165, 170))
    return s.outline()


def cup(coffee, foam=None, big=False):
    s = Sprite()
    h = 9 if big else 7
    top = 21 - h - 3
    s.trapezoid(top, top + h, 7 if big else 6, 5 if big else 4, 11, WHITE)
    s.rect(11 - 8, top - 1, 11 + 8, top, WHITE)
    s.rect(11 - 7, top, 11 + 7, top + 1, coffee)
    if foam == "heart":
        s.rect(9, top, 10, top + 1, CREAM), s.rect(12, top, 13, top + 1, CREAM), s.rect(10, top + 1, 12, top + 1, CREAM)
    elif foam == "foam":
        s.rect(4, top, 18, top + 1, CREAM)
    s.rect(18, top + 2, 21, top + 4, WHITE)
    s.rect(3, top + h + 1, 19, top + h + 2, GREY)
    s.set(8, top - 4, GREY), s.set(9, top - 5, GREY), s.set(13, top - 4, GREY), s.set(14, top - 5, GREY)
    return s.outline()


def latte():
    s = Sprite()
    s.trapezoid(3, 20, 6, 5, 12, C(235, 245, 250))
    s.trapezoid(5, 8, 5, 5, 12, CREAM)
    s.trapezoid(9, 13, 5, 5, 12, CHOCO)
    s.trapezoid(14, 19, 5, 4, 12, CREAM)
    s.rect(4, 2, 19, 3, WHITE)
    s.rect(6, 21, 17, 21, GREY)
    return s.outline()


def flame():
    """Two-tone flame of the 'by Baursak' mark (blue left, red right)."""
    s = Sprite()
    rows = [(13, 13), (12, 14), (12, 14), (11, 15), (10, 15), (10, 16), (9, 16), (8, 17), (7, 17), (6, 18),
            (5, 18), (4, 19), (3, 19), (3, 20), (3, 20), (3, 20), (4, 19), (4, 19), (5, 18), (6, 17), (8, 15)]
    for i, (x0, x1) in enumerate(rows):
        y = 1 + i
        lean = round(max(0, 10 - i) * 0.5)          # the tip flicks to the right like the logo's flame
        for x in range(x0 + lean - (2 if i < 4 else 0), x1 + lean + 1):
            s.set(x, y, BLUE if x < 12 + (lean // 2) else RED)
    # lighter inner flame
    for i, (x0, x1) in enumerate([(12, 12), (11, 13), (10, 14), (10, 14), (9, 15), (9, 15), (10, 14), (11, 13)]):
        for x in range(x0, x1 + 1):
            s.set(x, 13 + i, C(120, 170, 255) if x < 12 else C(255, 140, 130))
    return s.outline()



# ----------------------------------------------------------------- splash screen parts

LW = 26  # all burger layers share this width so they stack without alignment work


def layer(kind):
    h = {"bun_top": 12, "lettuce": 5, "tomato": 4, "cheese": 5, "patty": 6, "bun_bottom": 6}[kind]
    s = Sprite(LW, h)
    if kind == "bun_top":
        s.ellipse(13, 10, 11.4, 8.6, BUN)
        s.rect(2, 9, 23, 10, BUN)
        s.rect(3, 10, 22, 10, BUN_D)
        for x, y in ((8, 4), (13, 3), (18, 4), (10, 6), (15, 6), (6, 7), (20, 7)):
            s.set(x, y, SESAME)
    elif kind == "lettuce":
        s.rect(1, 1, 24, 2, LETTUCE)
        for x in range(1, 25, 3):
            s.set(x, 3, LETTUCE_L)
            s.set(x + 1, 3, LETTUCE)
        s.set(0, 2, LETTUCE)
        s.set(25, 2, LETTUCE)
    elif kind == "tomato":
        s.rect(2, 1, 23, 2, TOMATO)
        for x in (6, 12, 18):
            s.set(x, 1, C(255, 120, 100))
    elif kind == "cheese":
        s.rect(1, 1, 24, 2, CHEESE)
        s.rect(2, 3, 5, 3, CHEESE_D)
        s.rect(9, 3, 12, 3, CHEESE)
        s.rect(17, 3, 21, 3, CHEESE_D)
        s.rect(10, 4, 11, 4, CHEESE)
    elif kind == "patty":
        s.rect(1, 1, 24, 4, PATTY)
        for x in range(3, 24, 4):
            s.set(x, 2, PATTY_L)
            s.set(x + 2, 3, PATTY_L)
    elif kind == "bun_bottom":
        s.rect(2, 1, 23, 3, BUN_D)
        s.rect(3, 4, 22, 4, BUN_D)
        s.rect(1, 1, 24, 2, BUN)
    return s.outline()


def truck():
    """The Bonch food truck, side view, 48x30."""
    s = Sprite(48, 30)
    BODY, BODY_D = C(245, 243, 236), C(205, 205, 200)
    s.rect(2, 6, 45, 22, BODY)
    s.rect(1, 8, 46, 20, BODY)
    s.rect(2, 21, 45, 22, BODY_D)
    s.rect(2, 4, 45, 5, YELLOW)                       # warm LED strip on the roof
    s.rect(4, 5, 43, 5, C(255, 232, 120))
    s.rect(8, 9, 28, 17, C(30, 38, 48))               # serving window
    s.rect(9, 10, 27, 11, C(60, 74, 90))
    s.rect(7, 7, 29, 8, ORANGE)                       # awning
    for x in range(7, 30, 4):
        s.rect(x, 7, x + 1, 8, WHITE)
    s.rect(7, 18, 29, 19, BROWN)                      # counter
    s.rect(32, 10, 43, 16, YELLOW)                    # BONCH plate
    for x in (33, 36, 39, 42):
        s.rect(x, 12, x, 14, INK)
    s.rect(34, 13, 35, 13, INK), s.rect(37, 13, 38, 13, INK), s.rect(40, 13, 41, 13, INK)
    s.set(43, 10, ORANGE)
    for x in range(3, 46, 3):                         # pixel band along the bottom
        s.set(x, 21, [GREEN, YELLOW, ORANGE][(x // 3) % 3])
        s.set(x + 1, 21, [GREEN, YELLOW, ORANGE][(x // 3) % 3])
    for cx in (11, 36):                               # wheels
        s.ellipse(cx, 24, 4.2, 4.2, INK)
        s.ellipse(cx, 24, 1.8, 1.8, GREY)
    return s.outline()


def pin():
    """Map pin for the 'share location' button."""
    s = Sprite()
    rows = [(9, 14), (7, 16), (6, 17), (5, 18), (5, 18), (5, 18), (5, 18), (6, 17), (6, 17), (7, 16), (7, 16),
            (8, 15), (8, 15), (9, 14), (10, 13), (11, 12), (11, 12)]
    for i, (x0, x1) in enumerate(rows):
        for x in range(x0, x1 + 1):
            s.set(x, 2 + i, RED)
    s.rect(7, 5, 8, 7, C(255, 150, 140))
    s.rect(10, 6, 13, 9, WHITE)
    return s.outline()


SPRITES = {
    "burger_classic": lambda: burger(["lettuce", "tomato", "onion", "patty"]),
    "burger_cheese": lambda: burger(["lettuce", "tomato", "cheese", "patty"]),
    "burger_double": lambda: burger(["tomato", "cheese", "patty", "cheese", "patty"]),
    "burger_chicken": lambda: burger(["lettuce", "tomato", "chicken"]),
    "hotdog_classic": lambda: hotdog("classic"),
    "hotdog_cheese": lambda: hotdog("cheese"),
    "hotdog_hunter": lambda: hotdog("hunter"),
    "hotdog_spicy": lambda: hotdog("spicy"),
    "fries_s": lambda: fries("s"),
    "fries_m": lambda: fries("m"),
    "fries_l": lambda: fries("l"),
    "nuggets": nuggets,
    "wings": wings,
    "sauce_ketchup": lambda: sauce(RED, RED_D),
    "sauce_mayo": lambda: sauce(CREAM, C(220, 200, 150)),
    "sauce_cheese": lambda: sauce(CHEESE, CHEESE_D),
    "sauce_bbq": lambda: sauce(BROWN, BROWN_D),
    "sauce_garlic": lambda: sauce(WHITE, GREY, "garlic"),
    "sauce_hot": lambda: sauce(ORANGE, RED, "hot"),
    "shake_vanilla": lambda: shake(CREAM, C(220, 200, 150)),
    "shake_choco": lambda: shake(CHOCO, C(70, 40, 24)),
    "shake_straw": lambda: shake(PINK, C(220, 110, 140)),
    "drink_cola": lambda: can(BLUE, BLUE_D, BLUE_L),
    "drink_orange": lambda: can(ORANGE, C(200, 80, 10), C(255, 170, 90)),
    "drink_lime": lambda: can(C(40, 160, 70), C(24, 110, 46), C(130, 220, 130)),
    "drink_water": lambda: bottle(C(170, 215, 245), WHITE, C(60, 130, 220)),
    "drink_icetea": lambda: bottle(C(204, 132, 40), RED, YELLOW),
    "juice_orange": lambda: juice(ORANGE, "slice"),
    "juice_grapefruit": lambda: juice(C(244, 120, 130), "slice"),
    "juice_pomegranate": lambda: juice(C(160, 24, 50), "seeds"),
    "juice_apple": lambda: juice(C(190, 220, 90), "apple"),
    "juice_carrot": lambda: juice(C(240, 130, 30), "carrot"),
    "juice_apple_carrot": lambda: juice(C(236, 170, 50), "both"),
    "tea_cup": lambda: tea_glass(C(190, 100, 30)),
    "tea_pot": teapot,
    "tea_black": lambda: tea_glass(C(120, 56, 24)),
    "tea_green": lambda: tea_glass(C(150, 190, 70)),
    "espresso": lambda: cup(C(70, 40, 24)),
    "americano": lambda: cup(C(90, 54, 30), big=True),
    "latte": latte,
    "cappuccino": lambda: cup(C(120, 74, 40), "heart", big=True),
    "flame": flame,
    "layer_bun_top": lambda: layer("bun_top"),
    "layer_lettuce": lambda: layer("lettuce"),
    "layer_tomato": lambda: layer("tomato"),
    "layer_cheese": lambda: layer("cheese"),
    "layer_patty": lambda: layer("patty"),
    "layer_bun_bottom": lambda: layer("bun_bottom"),
    "truck": truck,
    "pin": pin,
}


def band_tile():
    """The green/yellow/orange pixel band from the food truck, as a repeating 48x8 tile."""
    import random
    rnd = random.Random(11)
    pal = [YELLOW] * 4 + [GREEN] * 3 + [ORANGE] + [BROWN]
    img = Image.new("RGBA", (48, 8), (0, 0, 0, 0))
    for cy in range(2):
        for cx in range(12):
            if rnd.random() < 0.82:
                c = rnd.choice(pal)
                for y in range(4):
                    for x in range(4):
                        img.putpixel((cx * 4 + x, cy * 4 + y), c)
    return img


def main():
    os.makedirs(OUT, exist_ok=True)
    band_tile().save(os.path.join(OUT, "band.png"))
    names = list(SPRITES)
    for name in names:
        SPRITES[name]().image().save(os.path.join(OUT, f"{name}.png"))
    # preview sheet (x6 scale) for a quick visual check
    cols = 8
    rows = (len(names) + cols - 1) // cols
    scale = 6
    sheet = Image.new("RGBA", (cols * N * scale, rows * N * scale), (255, 251, 234, 255))
    for i, name in enumerate(names):
        img = Image.open(os.path.join(OUT, f"{name}.png"))
        img = img.resize((img.width * scale // 2 if img.width > N else img.width * scale, img.height * scale // 2 if img.width > N else img.height * scale), Image.NEAREST)
        sheet.alpha_composite(img, ((i % cols) * N * scale, (i // cols) * N * scale))
    sheet.save(os.path.join(os.path.dirname(__file__), "..", "sprite_preview.png"))
    print(len(names), "sprites ->", os.path.normpath(OUT))


if __name__ == "__main__":
    sys.exit(main())
