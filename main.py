#!/usr/bin/env python3
"""news-image-20261118-v2 -- one image summing up Wednesday 18 Nov 2026.

A pure-stdlib Python program. It draws a 1024x1024 dark "atlas" magazine
cover -- masthead, a world map with numbered markers for each story, six
story cards with pictogram badges, and an "also making news" strip -- into
an RGB buffer, encodes it as a PNG with a hand-rolled encoder, and writes
it to $MAKEFUN_OUTPUT_DIR/entry.png (default /output).

Everything is drawn in code: a single-stroke vector font (glyphs defined
here as polylines on a 5x9 grid), polygon continents, and primitive
shapes. No network, no files read at runtime, no timestamps, no
randomness: two runs write byte-identical output.

=====================================================================
NEWS DATA -- copied from the main entry (the one permitted exception:
STORIES and ALSO_LINE are news data, not code). Content is NOT frozen
here; a separate job updates it on the evening of 19 Nov 2026 (WIB).
=====================================================================
"""

import math
import os
import struct
import zlib

# ------------------------------------------------------------------
# NEWS DATA (see the block above)
# ------------------------------------------------------------------

DATE_LINE = "WEDNESDAY 18 NOVEMBER 2026"
MASTHEAD = "THE WORLD TODAY"
SUBHEAD = "ONE DAY IN THE WORLD'S NEWS - SIX STORIES, EVERY REGION"

STORIES = [
    {
        "tag": "ASIA - SUMMITS",
        "color": (27, 108, 168),
        "icon": "summit",
        "title": "APEC OPENS AS TRUMP HEADS TO CHINA",
        "body": "Leaders gather in Shenzhen for the APEC summit. Trump "
                "travels on for a first-ever three-way meeting with Xi "
                "Jinping and Vladimir Putin, due on 19 November.",
    },
    {
        "tag": "ASIA-PACIFIC - SECURITY",
        "color": (14, 124, 102),
        "icon": "quad",
        "title": "QUAD ANNOUNCES NEW MARITIME PLAN",
        "body": "The US, India, Japan and Australia, meeting in Manila, "
                "unveil a new maritime exercise and joint work on AI "
                "and cybersecurity.",
    },
    {
        "tag": "EUROPE - WAR",
        "color": (169, 50, 38),
        "icon": "bridge",
        "title": "UKRAINE HITS CRIMEAN BRIDGE",
        "body": "Ukraine damaged the Crimean Bridge in a major strike, "
                "as Russia hit bridges around Kyiv, with both sides "
                "targeting crossings.",
    },
    {
        "tag": "MIDDLE EAST - CONFLICT",
        "color": (122, 62, 150),
        "icon": "radar",
        "title": "IRAN CLAIMS DRONE STRIKE ON US BASE",
        "body": "Iran's Revolutionary Guard said it hit a US military "
                "radar system at Sheikh Isa Air Base in Bahrain, its "
                "third strike on the country in five days.",
    },
    {
        "tag": "ASIA - DISASTER",
        "color": (93, 109, 126),
        "icon": "alert",
        "title": "RUSSIAN MILITARY PLANE CRASHES",
        "body": "A Russian military plane crashed in Siberia, killing "
                "19 people. Investigators are examining the wreckage "
                "to find the cause.",
    },
    {
        "tag": "EUROPE - DIPLOMACY",
        "color": (46, 125, 50),
        "icon": "ban",
        "title": "BRITAIN SANCTIONS SETTLEMENT FIRMS",
        "body": "Britain sanctioned Israeli settlement firms in a push "
                "to protect the two-state solution, targeting companies "
                "linked to West Bank settlements.",
    },
]

ALSO_LINE = ("ALSO MAKING NEWS: US loses measles-free status, health "
             "officials say - Cyclone Akvan nears India's Andhra coast, "
             "landfall due 20 Nov - Dhoni retires from the IPL and "
             "becomes CSK mentor - Mongolia's president resigns amid "
             "graft charges.")

SOURCE_LINE = "Sources: wire reports of 18 November 2026."

# Story locations on the map: (longitude, latitude, label, label dx, dy).
MARKERS = [
    (114.0, 22.5, "SHENZHEN", -8, -26),
    (121.0, 14.6, "MANILA", 14, 8),
    (33.5, 45.0, "CRIMEA", -6, -26),
    (50.5, 26.2, "BAHRAIN", 14, 6),
    (105.0, 62.0, "SIBERIA", -10, -26),
    (35.2, 31.9, "WEST BANK", -88, 8),
]

# ------------------------------------------------------------------
# Palette (dark atlas theme)
# ------------------------------------------------------------------

BG = (13, 30, 38)
PANEL = (21, 44, 53)
PANEL2 = (25, 51, 61)
PAPER = (244, 241, 232)
BODY_TEXT = (196, 212, 216)
MUTED = (158, 180, 186)
FAINT = (96, 122, 131)
CORAL = (255, 107, 74)
CORAL_DARK = (214, 74, 48)
GOLD = (242, 183, 70)
TEAL = (64, 190, 178)
LAND = (70, 138, 120)
LAND_EDGE = (96, 168, 148)
GRID = (38, 68, 80)
OCEAN_DOT = (33, 60, 70)
BORDER = (48, 78, 90)
WHITE = (255, 255, 255)
BLACK = (8, 18, 23)


def lighten(color, f=0.30):
    """Blend a colour toward white so it stays readable on dark panels."""
    return tuple(round(c + (255 - c) * f) for c in color)


# ------------------------------------------------------------------
# Single-stroke vector font.
# Each glyph is a tuple of strokes; a stroke is a polyline of (x, y)
# points on a 5-wide by 9-tall grid. Cap height rows 0..6, baseline 6,
# descenders reach row 8, x-height rows 2..6. Advance is 6 units.
# ------------------------------------------------------------------

FONT = {
    "A": (((0, 6), (2, 0), (4, 6)), ((1, 4), (3, 4))),
    "B": (((0, 0), (0, 6)), ((0, 0), (3, 0), (4, 1), (4, 2), (3, 2), (0, 2)),
          ((0, 2), (3, 2), (4, 3), (4, 5), (3, 6), (0, 6))),
    "C": (((4, 1), (3, 0), (1, 0), (0, 1), (0, 5), (1, 6), (3, 6), (4, 5)),),
    "D": (((0, 0), (0, 6), (3, 6), (4, 5), (4, 1), (3, 0), (0, 0)),),
    "E": (((4, 0), (0, 0), (0, 6), (4, 6)), ((0, 3), (3, 3))),
    "F": (((4, 0), (0, 0), (0, 6)), ((0, 3), (3, 3))),
    "G": (((4, 1), (3, 0), (1, 0), (0, 1), (0, 5), (1, 6), (3, 6), (4, 5),
           (4, 3), (2, 3)),),
    "H": (((0, 0), (0, 6)), ((4, 0), (4, 6)), ((0, 3), (4, 3))),
    "I": (((2, 0), (2, 6)), ((0, 0), (4, 0)), ((0, 6), (4, 6))),
    "J": (((4, 0), (4, 5), (3, 6), (1, 6), (0, 5)),),
    "K": (((0, 0), (0, 6)), ((4, 0), (0, 3), (4, 6))),
    "L": (((0, 0), (0, 6), (4, 6)),),
    "M": (((0, 6), (0, 0), (2, 3), (4, 0), (4, 6)),),
    "N": (((0, 6), (0, 0), (4, 6), (4, 0)),),
    "O": (((1, 0), (3, 0), (4, 1), (4, 5), (3, 6), (1, 6), (0, 5), (0, 1),
           (1, 0)),),
    "P": (((0, 6), (0, 0), (3, 0), (4, 1), (4, 2), (3, 3), (0, 3)),),
    "Q": (((1, 0), (3, 0), (4, 1), (4, 5), (3, 6), (1, 6), (0, 5), (0, 1),
           (1, 0)), ((2, 4), (4, 6))),
    "R": (((0, 6), (0, 0), (3, 0), (4, 1), (4, 2), (3, 3), (0, 3)),
          ((2, 3), (4, 6))),
    "S": (((4, 1), (3, 0), (1, 0), (0, 1), (0, 2), (1, 3), (3, 3), (4, 4),
           (4, 5), (3, 6), (1, 6), (0, 5)),),
    "T": (((0, 0), (4, 0)), ((2, 0), (2, 6))),
    "U": (((0, 0), (0, 5), (1, 6), (3, 6), (4, 5), (4, 0)),),
    "V": (((0, 0), (2, 6), (4, 0)),),
    "W": (((0, 0), (1, 6), (2, 3), (3, 6), (4, 0)),),
    "X": (((0, 0), (4, 6)), ((4, 0), (0, 6))),
    "Y": (((0, 0), (2, 3), (4, 0)), ((2, 3), (2, 6))),
    "Z": (((0, 0), (4, 0), (0, 6), (4, 6)),),
    "a": (((4, 2), (4, 6)), ((4, 3), (3, 2), (1, 2), (0, 3), (0, 5), (1, 6),
           (3, 6), (4, 5))),
    "b": (((0, 0), (0, 6)), ((0, 3), (2, 2), (3, 3), (4, 4), (4, 5), (3, 6),
           (0, 6))),
    "c": (((4, 3), (3, 2), (1, 2), (0, 3), (0, 5), (1, 6), (3, 6), (4, 5)),),
    "d": (((4, 0), (4, 6)), ((4, 3), (3, 2), (1, 2), (0, 3), (0, 5), (1, 6),
           (3, 6), (4, 5))),
    "e": (((4, 5), (3, 6), (1, 6), (0, 5), (0, 3), (1, 2), (3, 2), (4, 3),
           (4, 4), (0, 4)),),
    "f": (((3, 0), (2, 0), (1, 1), (1, 6)), ((0, 3), (3, 3))),
    "g": (((3, 2), (1, 2), (0, 3), (0, 5), (1, 6), (3, 6), (4, 5), (4, 3)),
          ((4, 5), (4, 7), (3, 8), (1, 8), (0, 7))),
    "h": (((0, 0), (0, 6)), ((0, 3), (2, 2), (3, 3), (4, 4), (4, 6))),
    "i": (((2, 0), (2, 1)), ((2, 2), (2, 6))),
    "j": (((3, 0), (3, 1)), ((3, 2), (3, 7), (2, 8), (1, 8), (0, 7))),
    "k": (((0, 0), (0, 6)), ((4, 2), (0, 4), (4, 6))),
    "l": (((1, 0), (1, 6)),),
    "m": (((0, 6), (0, 2), (1, 2), (2, 3), (2, 6)),
          ((2, 3), (3, 2), (4, 3), (4, 6))),
    "n": (((0, 6), (0, 2), (1, 2), (2, 2), (3, 3), (4, 4), (4, 6)),),
    "o": (((1, 2), (3, 2), (4, 3), (4, 5), (3, 6), (1, 6), (0, 5), (0, 3),
           (1, 2)),),
    "p": (((0, 2), (0, 8)), ((0, 3), (2, 2), (3, 3), (4, 4), (4, 5), (3, 6),
           (0, 6))),
    "q": (((4, 2), (4, 8)), ((4, 3), (2, 2), (1, 3), (0, 4), (0, 5), (1, 6),
           (4, 6))),
    "r": (((0, 6), (0, 2)), ((0, 3), (2, 2), (3, 3), (4, 3))),
    "s": (((4, 3), (3, 2), (1, 2), (0, 3), (1, 4), (3, 4), (4, 5), (3, 6),
           (1, 6), (0, 5)),),
    "t": (((2, 0), (2, 6)), ((0, 3), (3, 3)), ((2, 6), (3, 6))),
    "u": (((0, 2), (0, 5), (1, 6), (3, 6), (4, 5), (4, 2)),),
    "v": (((0, 2), (2, 6), (4, 2)),),
    "w": (((0, 2), (1, 6), (2, 4), (3, 6), (4, 2)),),
    "x": (((0, 2), (4, 6)), ((4, 2), (0, 6))),
    "y": (((0, 2), (2, 5), (4, 2)), ((4, 2), (3, 5), (2, 6), (2, 8), (1, 8))),
    "z": (((0, 2), (4, 2), (0, 6), (4, 6)),),
    "0": (((1, 0), (3, 0), (4, 1), (4, 5), (3, 6), (1, 6), (0, 5), (0, 1),
           (1, 0)),),
    "1": (((1, 0), (2, 0), (2, 6)), ((0, 6), (4, 6))),
    "2": (((0, 1), (1, 0), (3, 0), (4, 1), (4, 3), (0, 6), (4, 6)),),
    "3": (((0, 0), (4, 0), (4, 2), (3, 3), (4, 4), (4, 5), (3, 6), (0, 6)),
          ((1, 3), (3, 3))),
    "4": (((0, 4), (3, 0), (3, 6)), ((0, 4), (4, 4))),
    "5": (((4, 0), (0, 0), (0, 3), (3, 3), (4, 4), (4, 5), (3, 6), (0, 6)),),
    "6": (((3, 0), (1, 0), (0, 2), (0, 5), (1, 6), (3, 6), (4, 5), (4, 3),
           (2, 3), (0, 3)),),
    "7": (((0, 0), (4, 0), (2, 6)),),
    "8": (((1, 0), (3, 0), (4, 1), (4, 2), (3, 3), (1, 3), (0, 2), (0, 1),
           (1, 0)),
          ((1, 3), (3, 3), (4, 4), (4, 5), (3, 6), (1, 6), (0, 5), (0, 4),
           (1, 3))),
    "9": (((4, 6), (4, 1), (3, 0), (1, 0), (0, 1), (0, 3), (1, 4), (3, 4),
           (4, 3)),),
    " ": (),
    ".": (((2, 6), (2, 6)),),
    ",": (((2, 5), (2, 6), (1, 7)),),
    ":": (((2, 1), (2, 1)), ((2, 5), (2, 5))),
    ";": (((2, 1), (2, 1)), ((2, 5), (2, 6), (1, 7))),
    "!": (((2, 0), (2, 4)), ((2, 6), (2, 6))),
    "?": (((1, 0), (3, 0), (4, 1), (4, 2), (3, 3), (2, 4)), ((2, 6), (2, 6))),
    "'": (((2, 0), (2, 2), (1, 3)),),
    '"': (((1, 0), (1, 2)), ((3, 0), (3, 2))),
    "-": (((0, 3), (4, 3)),),
    "(": (((2, 0), (1, 1), (0, 3), (1, 5), (2, 6)),),
    ")": (((2, 0), (3, 1), (4, 3), (3, 5), (2, 6)),),
    "/": (((4, 6), (0, 0)),),
    "%": (((1, 1), (1, 1)), ((3, 5), (3, 5)), ((4, 0), (0, 6))),
    "&": (((3, 0), (2, 0), (1, 1), (1, 2), (2, 3), (3, 3), (4, 4), (4, 5),
           (3, 6), (1, 6), (0, 5), (0, 4), (2, 2), (4, 0)),),
    "+": (((2, 1), (2, 5)), ((0, 3), (4, 3))),
    "=": (((0, 2), (4, 2)), ((0, 4), (4, 4))),
    "*": (((2, 0), (2, 6)), ((0, 2), (4, 4)), ((4, 2), (0, 4))),
    "#": (((1, 0), (1, 6)), ((3, 0), (3, 6)), ((0, 2), (4, 2)),
          ((0, 4), (4, 4))),
    "@": (((3, 1), (4, 2), (4, 4), (3, 5), (1, 5), (0, 4), (0, 2), (1, 1),
           (3, 1)), ((2, 3), (3, 3), (3, 4), (2, 4))),
    "_": (((0, 6), (4, 6)),),
    "[": (((4, 0), (0, 0), (0, 6), (4, 6)),),
    "]": (((0, 0), (4, 0), (4, 6), (0, 6)),),
    "<": (((4, 1), (1, 3), (4, 5)),),
    ">": (((0, 1), (3, 3), (0, 5)),),
    "$": (((2, 0), (2, 6)),
          ((4, 1), (3, 0), (1, 0), (0, 1), (0, 2), (1, 3), (3, 3), (4, 4),
           (4, 5), (3, 6), (1, 6), (0, 5))),
}

# ------------------------------------------------------------------
# Canvas: RGB buffer with drawing helpers
# ------------------------------------------------------------------

W, H = 1024, 1024


class Screen:
    def __init__(self, w, h, bg):
        self.w = w
        self.h = h
        self.buf = bytearray(w * h * 3)
        self.paint(0, 0, w, h, bg)

    def _row(self, y):
        return y * self.w * 3

    def dot(self, x, y, color):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = self._row(y) + x * 3
            self.buf[i], self.buf[i + 1], self.buf[i + 2] = color

    def paint(self, x, y, w, h, color):
        """Fill a rectangle, clipped to the canvas (fast row slices)."""
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.w, x + w), min(self.h, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(color) * (x1 - x0)
        for yy in range(y0, y1):
            base = self._row(yy) + x0 * 3
            self.buf[base:base + len(row)] = row

    def frame(self, x, y, w, h, color, t=1):
        self.paint(x, y, w, t, color)
        self.paint(x, y + h - t, w, t, color)
        self.paint(x, y, t, h, color)
        self.paint(x + w - t, y, t, h, color)

    def hline(self, x, y, w, color, t=1):
        self.paint(x, y - t // 2, w, t, color)

    def seg(self, x0, y0, x1, y1, color, t=1):
        """Bresenham segment with a square brush of thickness t."""
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        half = t // 2
        while True:
            self.paint(x0 - half, y0 - half, t, t, color)
            if x0 == x1 and y0 == y1:
                return
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def poly(self, pts, color, t=1, closed=False):
        for i in range(len(pts) - 1):
            self.seg(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1],
                     color, t)
        if closed and len(pts) > 2:
            self.seg(pts[-1][0], pts[-1][1], pts[0][0], pts[0][1], color, t)

    def disc(self, cx, cy, r, color):
        """Filled disc via horizontal spans."""
        for dy in range(-r, r + 1):
            half = int(math.sqrt(max(0, r * r - dy * dy)))
            self.paint(cx - half, cy + dy, 2 * half + 1, 1, color)

    def ring(self, cx, cy, r, color, t=2):
        steps = max(24, int(2 * math.pi * r))
        prev = None
        for i in range(steps + 1):
            a = 2 * math.pi * i / steps
            px = round(cx + r * math.cos(a))
            py = round(cy + r * math.sin(a))
            if prev is not None:
                self.seg(prev[0], prev[1], px, py, color, t)
            prev = (px, py)

    def arc(self, cx, cy, r, a0, a1, color, t=2):
        """Arc from a0 to a1 degrees (0 = east, y grows downward)."""
        steps = max(6, int(abs(a1 - a0) * r / 10))
        prev = None
        for i in range(steps + 1):
            a = math.radians(a0 + (a1 - a0) * i / steps)
            px = round(cx + r * math.cos(a))
            py = round(cy + r * math.sin(a))
            if prev is not None:
                self.seg(prev[0], prev[1], px, py, color, t)
            prev = (px, py)

    def fill_poly(self, pts, color):
        """Even-odd scanline fill of a polygon given as (x, y) ints."""
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        for y in range(max(0, min(ys)), min(self.h - 1, max(ys)) + 1):
            xs = []
            n = len(pts)
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if (y0 <= y < y1) or (y1 <= y < y0):
                    xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                xa, xb = int(math.ceil(xs[i])), int(math.floor(xs[i + 1]))
                if xb >= xa:
                    self.paint(xa, y, xb - xa + 1, 1, color)

    def rounded(self, x, y, w, h, r, color):
        """Filled rectangle with rounded corners of radius r."""
        self.paint(x + r, y, w - 2 * r, h, color)
        self.paint(x, y + r, w, h - 2 * r, color)
        for cx, cy in ((x + r, y + r), (x + w - r - 1, y + r),
                       (x + r, y + h - r - 1), (x + w - r - 1, y + h - r - 1)):
            self.disc(cx, cy, r, color)

    def speckle(self, x, y, w, h, count, seed, amp=9):
        """Deterministic low-contrast grain (print texture + PNG weight)."""
        state = seed & 0x7FFFFFFF
        for _ in range(count):
            state = (1103515245 * state + 12345) & 0x7FFFFFFF
            px = x + state % w
            state = (1103515245 * state + 12345) & 0x7FFFFFFF
            py = y + state % h
            state = (1103515245 * state + 12345) & 0x7FFFFFFF
            d = (state % (2 * amp + 1)) - amp
            i = self._row(py) + px * 3
            for c in range(3):
                v = self.buf[i + c] + d
                self.buf[i + c] = 0 if v < 0 else (255 if v > 255 else v)


# ------------------------------------------------------------------
# Text: measurement, wrapping, rendering of the stroke font
# ------------------------------------------------------------------

def text_w(text, scale):
    return int(round(len(text) * 6 * scale - scale)) if text else 0


def draw_text(cv, x, y, text, scale, color):
    """Draw text with its top-left at (x, y); y is the cap-height top."""
    t = max(1, int(round(scale * 0.55)))
    for ch in text:
        strokes = FONT.get(ch)
        if strokes is None:
            raise ValueError("character not in font: %r" % ch)
        for stroke in strokes:
            pts = [(int(round(x + gx * scale)), int(round(y + gy * scale)))
                   for gx, gy in stroke]
            if len(pts) == 1:
                cv.paint(pts[0][0] - t // 2, pts[0][1] - t // 2, t, t, color)
            else:
                cv.poly(pts, color, t)
        x += 6 * scale
    return x


def draw_text_c(cv, cx, y, text, scale, color):
    draw_text(cv, cx - text_w(text, scale) // 2, y, text, scale, color)


def wrap(text, scale, max_w):
    out = []
    for para in text.split("\n"):
        words = para.split(" ")
        cur = ""
        for word in words:
            trial = word if not cur else cur + " " + word
            if text_w(trial, scale) <= max_w:
                cur = trial
            else:
                if cur:
                    out.append(cur)
                cur = word
        if cur:
            out.append(cur)
    return out


# ------------------------------------------------------------------
# World map: continents as (lon, lat) polygons, equirectangular.
# ------------------------------------------------------------------

CONTINENTS = [
    # North America
    [(-168, 66), (-145, 70), (-130, 71), (-120, 72), (-110, 73), (-100, 73),
     (-95, 80), (-90, 74), (-85, 70), (-80, 73), (-75, 72), (-70, 62),
     (-65, 60), (-60, 55), (-55, 47), (-60, 45), (-65, 44), (-70, 42),
     (-75, 35), (-80, 32), (-81, 26), (-84, 30), (-90, 21), (-94, 17),
     (-97, 16), (-100, 18), (-105, 20), (-110, 23), (-114, 28), (-117, 33),
     (-122, 37), (-124, 42), (-124, 48), (-128, 52), (-135, 58), (-145, 60),
     (-155, 58), (-162, 58), (-168, 66)],
    # Greenland
    [(-58, 64), (-45, 60), (-32, 68), (-25, 70), (-22, 76), (-30, 80),
     (-45, 81), (-58, 78), (-62, 74), (-58, 64)],
    # South America
    [(-80, 9), (-77, 4), (-72, 11), (-64, 10), (-59, 8), (-52, 5), (-50, 0),
     (-44, -3), (-35, -8), (-38, -15), (-40, -22), (-48, -28), (-53, -33),
     (-58, -38), (-62, -41), (-65, -45), (-68, -50), (-70, -54), (-73, -50),
     (-73, -44), (-73, -37), (-71, -30), (-70, -20), (-75, -15), (-80, -6),
     (-81, 0), (-80, 9)],
    # Africa
    [(-17, 15), (-16, 20), (-10, 30), (-5, 35), (0, 36), (10, 37), (11, 34),
     (20, 32), (25, 32), (30, 31), (32, 31), (35, 28), (38, 20), (43, 12),
     (48, 11), (51, 12), (51, 10), (46, 5), (41, -2), (40, -10), (37, -18),
     (35, -24), (32, -29), (28, -33), (20, -35), (17, -32), (14, -22),
     (12, -18), (13, -12), (12, -6), (9, 0), (9, 4), (4, 6), (-8, 5),
     (-13, 8), (-17, 15)],
    # Eurasia
    [(-10, 36), (-9, 43), (-2, 44), (-2, 48), (0, 50), (4, 52), (7, 54),
     (8, 57), (10, 59), (12, 56), (18, 56), (21, 55), (24, 58), (26, 59),
     (28, 60), (30, 62), (32, 66), (34, 68), (40, 68), (45, 68), (52, 69),
     (58, 69), (66, 70), (72, 72), (78, 72), (85, 74), (95, 76), (105, 77),
     (113, 74), (120, 73), (128, 72), (135, 72), (142, 72), (150, 70),
     (158, 69), (162, 66), (170, 66), (178, 65), (175, 62), (170, 60),
     (162, 58), (158, 52), (156, 51), (150, 59), (144, 59), (142, 55),
     (141, 50), (140, 45), (138, 43), (135, 42), (132, 43), (129, 38),
     (127, 40), (126, 38), (122, 38), (121, 32), (120, 28), (116, 23),
     (112, 22), (109, 18), (108, 12), (106, 10), (104, 9), (101, 7), (99, 9),
     (97, 15), (95, 16), (93, 20), (90, 22), (88, 22), (86, 20), (84, 19),
     (80, 15), (80, 13), (77, 8), (75, 12), (73, 16), (70, 20), (67, 24),
     (64, 25), (61, 25), (58, 26), (57, 27), (54, 27), (52, 28), (50, 29),
     (48, 30), (46, 30), (44, 29), (42, 30), (39, 31), (36, 36), (34, 36),
     (32, 36), (30, 36), (27, 37), (26, 39), (23, 36), (22, 37), (20, 40),
     (18, 40), (16, 42), (14, 44), (12, 44), (10, 44), (8, 44), (6, 43),
     (3, 43), (0, 44), (-2, 44), (-2, 48), (-5, 48), (-4, 44), (-2, 43),
     (-1, 40), (-2, 37), (-5, 36), (-9, 37), (-10, 36)],
    # United Kingdom
    [(-5, 50), (-3, 53), (-5, 56), (-3, 58), (-1, 57), (0, 52), (-2, 51),
     (-5, 50)],
    # Iceland
    [(-22, 64), (-18, 63), (-15, 64), (-14, 65), (-18, 66), (-22, 66),
     (-22, 64)],
    # Japan
    [(130, 31), (132, 33), (134, 34), (136, 35), (138, 35), (139, 37),
     (140, 39), (141, 41), (142, 43), (144, 44), (143, 45), (141, 44),
     (140, 40), (139, 37), (137, 35), (135, 33), (133, 34), (131, 33),
     (130, 31)],
    # Sumatra
    [(95, 5), (97, 3), (100, 0), (103, -2), (105, -4), (106, -6), (104, -6),
     (101, -3), (98, 1), (95, 5)],
    # Borneo
    [(109, 1), (111, 3), (114, 4), (117, 3), (118, 1), (118, -3), (116, -4),
     (113, -3), (110, -3), (109, 1)],
    # New Guinea
    [(131, -1), (134, -2), (137, -2), (140, -3), (141, -3), (141, -7),
     (139, -8), (136, -8), (133, -7), (131, -4), (131, -1)],
    # Madagascar
    [(44, -16), (47, -15), (50, -17), (49, -20), (47, -23), (45, -25),
     (44, -22), (43, -19), (44, -16)],
    # New Zealand
    [(167, -45), (169, -43), (171, -41), (173, -40), (175, -38), (177, -38),
     (178, -37), (176, -40), (174, -42), (171, -44), (168, -46), (167, -45)],
    # Sri Lanka
    [(80, 9), (81, 8), (81, 6), (80, 6), (80, 9)],
]


def project(lon, lat, mx, my, mw, mh):
    """Equirectangular projection into the map box; lat 78..-58."""
    x = mx + (lon + 180.0) / 360.0 * mw
    y = my + (78.0 - lat) / 136.0 * mh
    return int(round(x)), int(round(y))


# ------------------------------------------------------------------
# Icons: white pictograms in a 44x44 box, drawn with primitives.
# ------------------------------------------------------------------

def draw_icon(cv, kind, bx, by, color):
    """Accent badge + white pictogram for one story kind."""
    cv.rounded(bx, by, 44, 44, 9, color)
    ink = WHITE
    if kind == "summit":
        # Three pennant flags on poles, over a base line.
        for px in (12, 22, 32):
            cv.seg(bx + px, by + 34, bx + px, by + 12, ink, 2)
            cv.fill_poly([(bx + px, by + 12), (bx + px + 11, by + 15),
                          (bx + px, by + 18)], ink)
        cv.seg(bx + 6, by + 38, bx + 38, by + 38, ink, 2)
    elif kind == "quad":
        # Four diamonds in a square, over two waves.
        for cx, cy in ((12, 14), (32, 14), (12, 30), (32, 30)):
            cv.fill_poly([(bx + cx, by + cy - 5), (bx + cx + 5, by + cy),
                          (bx + cx, by + cy + 5), (bx + cx - 5, by + cy)],
                         ink)
        cv.poly([(bx + 6, by + 40), (bx + 12, by + 37), (bx + 18, by + 40),
                 (bx + 24, by + 37), (bx + 30, by + 40), (bx + 36, by + 37)],
                ink, 2)
    elif kind == "bridge":
        # Suspension bridge: towers, deck, cable, suspenders.
        cv.seg(bx + 12, by + 10, bx + 12, by + 34, ink, 3)
        cv.seg(bx + 32, by + 10, bx + 32, by + 34, ink, 3)
        cv.seg(bx + 4, by + 34, bx + 40, by + 34, ink, 3)
        cv.poly([(bx + 4, by + 14), (bx + 12, by + 10), (bx + 22, by + 24),
                 (bx + 32, by + 10), (bx + 40, by + 14)], ink, 2)
        for sx, sy in ((17, 17), (22, 24), (27, 17)):
            cv.seg(bx + sx, by + sy, bx + sx, by + 34, ink, 1)
    elif kind == "radar":
        # Quarter radar arcs, sweep line and blip.
        cx, cy = bx + 12, by + 34
        for r in (10, 17, 24):
            cv.arc(cx, cy, r, -90, 0, ink, 2)
        cv.seg(cx, cy, bx + 32, by + 14, ink, 2)
        cv.disc(bx + 28, by + 18, 3, ink)
        cv.disc(cx, cy, 2, ink)
    elif kind == "alert":
        # Plane in flight, nose up.
        cv.fill_poly([(bx + 8, by + 26), (bx + 5, by + 14), (bx + 13, by + 22)],
                     ink)
        cv.seg(bx + 8, by + 26, bx + 36, by + 20, ink, 3)
        cv.seg(bx + 20, by + 23, bx + 30, by + 33, ink, 3)
        cv.seg(bx + 4, by + 32, bx + 10, by + 31, ink, 2)
    elif kind == "ban":
        # Office block under a prohibition slash.
        cv.frame(bx + 12, by + 8, 20, 28, ink, 2)
        for wx in (17, 23):
            for wy in (13, 20, 27):
                cv.paint(bx + wx, by + wy, 3, 3, ink)
        cv.seg(bx + 8, by + 38, bx + 36, by + 6, ink, 4)
    else:
        raise ValueError("unknown icon: %r" % kind)


# ------------------------------------------------------------------
# Layout
# ------------------------------------------------------------------

def draw_masthead(cv):
    cv.paint(0, 0, W, 6, CORAL)
    draw_text_c(cv, W // 2, 22, MASTHEAD, 7, PAPER)
    draw_text_c(cv, W // 2, 72, DATE_LINE, 3, CORAL)
    draw_text_c(cv, W // 2, 98, SUBHEAD, 2, MUTED)
    cv.paint(24, 122, W - 48, 3, CORAL)


def draw_map(cv):
    px, py, pw, ph = 24, 134, 976, 246
    cv.rounded(px, py, pw, ph, 12, PANEL)
    cv.speckle(px, py, pw, ph, 5000, 987654, amp=6)
    draw_text(cv, px + 16, py + 12, "WHERE THE DAY HAPPENED", 2, GOLD)
    mx, my, mw, mh = px + 16, py + 40, pw - 32, 188
    # Graticule every 30 degrees.
    for lon in range(-180, 181, 30):
        x, _ = project(lon, 0, mx, my, mw, mh)
        cv.paint(x, my, 1, mh, GRID)
    for lat in range(-60, 79, 30):
        _, y = project(0, lat, mx, my, mw, mh)
        cv.paint(mx, y, mw, 1, GRID)
    # Halftone dots across the ocean.
    for gx in range(mx + 6, mx + mw, 13):
        for gy in range(my + 6, my + mh, 13):
            cv.dot(gx, gy, OCEAN_DOT)
    # Continents.
    for poly in CONTINENTS:
        pts = [project(lon, lat, mx, my, mw, mh) for lon, lat in poly]
        cv.fill_poly(pts, LAND)
        cv.poly(pts, LAND_EDGE, 1, closed=True)
    # Numbered markers.
    for i, (lon, lat, label, dx, dy) in enumerate(MARKERS, 1):
        mxp, myp = project(lon, lat, mx, my, mw, mh)
        cv.disc(mxp, myp, 11, CORAL)
        cv.ring(mxp, myp, 11, PAPER, 2)
        draw_text_c(cv, mxp, myp - 6, str(i), 2, WHITE)
        draw_text(cv, mxp + dx, myp + dy, label, 1.5, PAPER)


def draw_card(cv, story, num, x, y, w, h):
    accent = lighten(story["color"], 0.30)
    cv.rounded(x, y, w, h, 8, PANEL2)
    cv.speckle(x, y, w, h, 900, 1000 + num * 77, amp=4)
    cv.frame(x, y, w, h, BORDER, 1)
    cv.paint(x, y + 8, 6, h - 16, accent)
    # Tag chip.
    chip_w = text_w(story["tag"], 2) + 20
    cv.rounded(x + 18, y + 12, chip_w, 20, 4, accent)
    draw_text(cv, x + 28, y + 16, story["tag"], 2, WHITE)
    # Icon badge + story number.
    bx, by = x + w - 58, y + 12
    draw_icon(cv, story["icon"], bx, by, accent)
    cv.disc(bx + 2, by + 2, 10, CORAL)
    cv.ring(bx + 2, by + 2, 10, BG, 2)
    draw_text_c(cv, bx + 2, by - 4, str(num), 2, WHITE)
    # Title, up to two lines.
    title_lines = wrap(story["title"], 2.5, w - 28 - 58)
    ty = y + 42
    for line in title_lines[:2]:
        draw_text(cv, x + 18, ty, line, 2.5, PAPER)
        ty += 18
    # Body, up to five lines.
    body_lines = wrap(story["body"], 2, w - 36)
    byy = ty + 6
    for line in body_lines[:5]:
        draw_text(cv, x + 18, byy, line, 2, BODY_TEXT)
        byy += 13


def draw_also(cv):
    x, y, w, h = 24, 884, 976, 100
    cv.rounded(x, y, w, h, 8, PANEL)
    cv.speckle(x, y, w, h, 700, 31337, amp=4)
    cv.frame(x, y, w, h, BORDER, 1)
    cv.paint(x + 16, y + 12, 10, 10, CORAL)
    draw_text(cv, x + 34, y + 10, "ALSO MAKING NEWS", 2, GOLD)
    items = ALSO_LINE[len("ALSO MAKING NEWS: "):].split(" - ")
    col_w = (w - 32) // 2
    for i, item in enumerate(items):
        col, row = i % 2, i // 2
        ix = x + 16 + col * col_w
        iy = y + 38 + row * 30
        cv.disc(ix + 4, iy + 5, 4, CORAL)
        lines = wrap(item, 2, col_w - 24)
        ly = iy
        for line in lines[:2]:
            draw_text(cv, ix + 16, ly, line, 2, PAPER)
            ly += 14


def draw_footer(cv):
    draw_text_c(cv, W // 2, 994, SOURCE_LINE, 2, FAINT)


def render():
    cv = Screen(W, H, BG)
    cv.speckle(0, 0, W, H, 16000, 424242, amp=8)
    draw_masthead(cv)
    draw_map(cv)
    cw, ch, gap = 480, 156, 16
    for i, story in enumerate(STORIES):
        col, row = i % 2, i // 2
        draw_card(cv, story, i + 1, 24 + col * (cw + gap),
                  392 + row * (ch + 8), cw, ch)
    draw_also(cv)
    draw_footer(cv)
    return cv


# ------------------------------------------------------------------
# Hand-rolled PNG encoder (filter 0, zlib level 9, no ancillary data)
# ------------------------------------------------------------------

def _chunk(kind, data):
    return (struct.pack(">I", len(data)) + kind + data +
            struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))


def encode_png(cv):
    raw = bytearray()
    for y in range(cv.h):
        raw.append(0)
        raw += cv.buf[y * cv.w * 3:(y + 1) * cv.w * 3]
    ihdr = struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) +
            _chunk(b"IDAT", zlib.compress(bytes(raw), 9)) +
            _chunk(b"IEND", b""))


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    data = encode_png(render())
    with open(os.path.join(out_dir, "entry.png"), "wb") as f:
        f.write(data)


if __name__ == "__main__":
    main()
