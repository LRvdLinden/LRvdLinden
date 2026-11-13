#!/usr/bin/env python3
"""
Pixel / terminal-style GitHub profile for LRvdLinden.

Builds every SVG in assets/ (dark + light) and README.md from:
  - the app list on https://lrvdlinden.app/apps.json (cached in data/apps.json)
  - the app icons on https://lrvdlinden.app/img/ (cached in data/icons/)
  - live GitHub numbers when GITHUB_TOKEN is set (cached in data/stats.json)

Run:  python scripts/build.py
Edit the texts below (WHOAMI, STACK, LINKS) to change what the profile says.
"""
import argparse
import base64
import datetime as dt
import html
import io
import json
import os
import shutil
import urllib.request

from fontTools import subset
from fontTools.ttLib import TTFont
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
DATA = os.path.join(ROOT, "data")
FONTS = os.path.join(ROOT, "scripts", "fonts")

USER = "LRvdLinden"
SITE = "https://lrvdlinden.app"
RAW = f"https://raw.githubusercontent.com/{USER}/{USER}"

LINKS = {
    "site": "https://lrvdlinden.app",
    "donate": "https://lrvdlinden.app/donate",
    "appstore": "https://apps.apple.com/nl/developer/leon-van-der-linden/id607860328",
    "homey_me": "https://homey.app/nl-nl/apps/author/5d4da77a2c836a50f6936070/page/0/",
    "homey_pf": "https://homey.app/nl-nl/apps/author/6ac4bc064c7de6266bbdb73e/page/0/",
    "community": "https://community.homey.app/t/apps-made-by-lrvdlinden/85452",
}

# ---------------------------------------------------------------- texts
TAGLINE = "> apps for iPhone, Apple TV, Android & Homey_"

def whoami_lines(counts):
    return [
        ("cmd", "whoami"),
        ("out", "léon van der linden · developer from the netherlands"),
        ("cmd", "cat focus.txt"),
        ("out", "» native apps for iPhone, iPad, Mac, Apple TV & Watch"),
        ("out", "» Homey apps that make the smart home a bit smarter"),
        ("out", "» Android, Windows & TV builds where it makes sense"),
        ("out", "» a website + admin dashboard behind every app"),
        ("cmd", "ls ~/labels"),
        ("dir", "LRvdLinden/    PixelForges/"),
        ("cmd", "./apps --status"),
        ("stat", counts),
        ("prompt", ""),
    ]

STACK = [
    ("SWIFT", "orange"), ("SWIFTUI", "blue"), ("SWIFTDATA", "purple"),
    ("CLOUDKIT", "blue"), ("KOTLIN", "purple"), ("JAVASCRIPT", "yellow"),
    ("NODE.JS", "green"), ("HOMEY SDK 3", "green"), ("HTML/CSS", "red"),
    ("PHP", "purple"), ("GITHUB ACTIONS", "blue"),
]

# ---------------------------------------------------------------- themes
THEMES = {
    "dark": dict(
        bg="#0d1117", panel="#0f1622", bar="#16202f", line="#29adff",
        text="#e6edf3", dim="#8b949e", faint="#1c2738", shadow="#05080d",
        green="#00e436", yellow="#ffec27", red="#ff004d", pink="#ff77a8",
        blue="#29adff", orange="#ffa300", purple="#a28bd4",
        wall="#5f574f", wall2="#4a433d", roof="#ff004d", roof2="#a3003a",
        door="#ab5236", win="#1d2b53", glass="#ffec27", trunk="#ab5236",
        leaf="#00e436", leaf2="#008751", grass="#008751", dirt="#3b2a22",
    ),
    "light": dict(
        bg="#ffffff", panel="#fbfcfe", bar="#eef2f8", line="#1d2b53",
        text="#1d2b53", dim="#5a6478", faint="#e7ecf3", shadow="#c7d1df",
        green="#00873c", yellow="#c79100", red="#d1003a", pink="#c2185b",
        blue="#1666c5", orange="#d86a00", purple="#6b4fbb",
        wall="#c2c3c7", wall2="#9a9ba3", roof="#ff004d", roof2="#a3003a",
        door="#ab5236", win="#5a6478", glass="#ffec27", trunk="#ab5236",
        leaf="#00b543", leaf2="#008751", grass="#00b543", dirt="#ab5236",
    ),
}
STATUS = {
    "live": ("LIVE", "green"),
    "beta": ("BETA", "yellow"),
    "dev": ("IN DEV", "pink"),
}

# ---------------------------------------------------------------- fonts
FONT_FILES = {"px": "PressStart2P.woff", "vt": "VT323.woff"}
FONT_FAMILY = {"px": "PX", "vt": "VT"}
ADV = {"px": 1.0, "vt": 0.4}  # both fonts are monospaced (advance in em)
_font_cache = {}


def text_width(s, font, size):
    return len(s) * ADV[font] * size


def font_face(font, chars):
    key = (font, "".join(sorted(chars)))
    if key in _font_cache:
        return _font_cache[key]
    f = TTFont(os.path.join(FONTS, FONT_FILES[font]))
    opts = subset.Options()
    opts.flavor = "woff"
    opts.layout_features = []
    opts.name_IDs = []
    opts.notdef_outline = True
    sub = subset.Subsetter(opts)
    sub.populate(text="".join(chars) + " ")
    sub.subset(f)
    buf = io.BytesIO()
    f.flavor = "woff"
    f.save(buf)
    b64 = base64.b64encode(buf.getvalue()).decode()
    css = (f"@font-face{{font-family:{FONT_FAMILY[font]};"
           f"src:url(data:font/woff;base64,{b64}) format('woff');}}")
    _font_cache[key] = css
    return css


# ---------------------------------------------------------------- canvas
class SVG:
    def __init__(self, w, h, theme, title):
        self.w, self.h, self.t, self.title = w, h, THEMES[theme], title
        self.els, self.defs, self.css = [], [], []
        self.chars = {"px": set(), "vt": set()}

    def c(self, name):
        return self.t.get(name, name)

    def rect(self, x, y, w, h, fill, cls=None, extra=""):
        if w <= 0 or h <= 0:
            return
        k = f' class="{cls}"' if cls else ""
        self.els.append(f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" '
                        f'fill="{self.c(fill)}"{k}{extra}/>')

    def text(self, x, y, s, font="vt", size=20, fill="text", anchor="start",
             cls=None, extra=""):
        self.chars[font].update(s)
        k = f' class="{cls}"' if cls else ""
        a = f' text-anchor="{anchor}"' if anchor != "start" else ""
        self.els.append(
            f'<text x="{x:g}" y="{y:g}" font-family="{FONT_FAMILY[font]}" '
            f'font-size="{size}" fill="{self.c(fill)}"{a}{k}{extra}>'
            f"{html.escape(s)}</text>")

    def raw(self, s):
        self.els.append(s)

    def box(self, x, y, w, h, fill="panel", stroke="line", u=4, shadow=True):
        """Panel with stepped (pixel) corners and a hard drop shadow."""
        if shadow:
            self._shape(x + u, y + u, w, h, "shadow", "shadow", u)
        self._shape(x, y, w, h, fill, stroke, u)

    def _shape(self, x, y, w, h, fill, stroke, u):
        self.rect(x + u, y + 2 * u, w - 2 * u, h - 4 * u, fill)
        self.rect(x + 2 * u, y + u, w - 4 * u, h - 2 * u, fill)
        for r in [(x + 2 * u, y, w - 4 * u, u), (x + 2 * u, y + h - u, w - 4 * u, u),
                  (x, y + 2 * u, u, h - 4 * u), (x + w - u, y + 2 * u, u, h - 4 * u),
                  (x + u, y + u, u, u), (x + w - 2 * u, y + u, u, u),
                  (x + u, y + h - 2 * u, u, u), (x + w - 2 * u, y + h - 2 * u, u, u)]:
            self.rect(*r, stroke)

    def sprite(self, rows, pal, x, y, px, cls=None):
        """rows: list of strings or lists; pal maps a char to a theme colour."""
        g = [f'<g{f" class={chr(34)}{cls}{chr(34)}" if cls else ""}>']
        for j, row in enumerate(rows):
            i = 0
            while i < len(row):
                ch = row[i]
                col = pal.get(ch) if isinstance(pal, dict) else ch
                if not col or ch in (".", " ", None):
                    i += 1
                    continue
                n = 1
                while i + n < len(row) and row[i + n] == ch:
                    n += 1
                g.append(f'<rect x="{x + i * px:g}" y="{y + j * px:g}" '
                         f'width="{n * px:g}" height="{px:g}" fill="{self.c(col)}"/>')
                i += n
        g.append("</g>")
        self.els.append("".join(g))

    def window(self, x, y, w, h, title):
        self.box(x, y, w, h)
        self.rect(x + 8, y + 8, w - 16, 28, "bar")
        self.rect(x + 4, y + 36, w - 8, 4, "line")
        for i, col in enumerate(["red", "yellow", "green"]):
            self.rect(x + 20 + i * 20, y + 16, 12, 12, col)
        self.text(x + w / 2, y + 30, title, "vt", 22, "dim", "middle")

    def render(self):
        faces = "".join(font_face(f, ch) for f, ch in self.chars.items() if ch)
        css = "".join(self.css)
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
                f'viewBox="0 0 {self.w} {self.h}" role="img" aria-label="{html.escape(self.title)}" '
                f'shape-rendering="crispEdges">'
                f"<title>{html.escape(self.title)}</title>"
                f"<style>{faces}{css}</style>"
                f'<defs>{"".join(self.defs)}</defs>'
                f'{"".join(self.els)}</svg>')


BLINK = ("@keyframes blink{0%,49%{opacity:1}50%,100%{opacity:0}}"
         ".blink{animation:blink 1.1s steps(1) infinite}")


# ---------------------------------------------------------------- data
def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": f"{USER}-profile-builder"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def load_apps(args):
    cache = os.path.join(DATA, "apps.json")
    raw = None
    if args.apps:
        raw = open(args.apps, "rb").read()
    elif not args.offline:
        try:
            raw = fetch(f"{SITE}/apps.json")
            json.loads(raw)
        except Exception as e:  # noqa: BLE001
            print("! apps.json not reachable, using cache:", e)
            raw = None
    if raw:
        with open(cache, "wb") as f:
            f.write(raw)
    return json.load(open(cache, encoding="utf-8"))["apps"]


def load_icon(app, args):
    name = os.path.basename(app.get("icon", ""))
    if not name:
        return None
    cache = os.path.join(DATA, "icons", name)
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    if args.img_dir and os.path.exists(os.path.join(args.img_dir, name)):
        shutil.copy(os.path.join(args.img_dir, name), cache)
    elif not args.offline and not os.path.exists(cache):
        try:
            with open(cache, "wb") as f:
                f.write(fetch(f"{SITE}/img/{name}"))
        except Exception as e:  # noqa: BLE001
            print("! icon not reachable:", name, e)
            if os.path.exists(cache) and os.path.getsize(cache) == 0:
                os.remove(cache)
    return cache if os.path.exists(cache) else None


def pixelate(path, n=16, colors=24):
    """Real app icon -> n x n pixel art with rounded (squircle) corners."""
    img = Image.open(path).convert("RGBA")
    # crop transparent padding so the artwork fills the tile
    bbox = img.getchannel("A").point(lambda a: 255 if a > 16 else 0).getbbox()
    if bbox:
        img = img.crop(bbox)
    img = img.resize((n, n), Image.Resampling.BOX)
    q = img.quantize(colors=colors, method=Image.Quantize.FASTOCTREE).convert("RGBA")
    r = n * 0.22
    rows = []
    for j in range(n):
        row = []
        for i in range(n):
            cx = r if i < r else (n - r if i >= n - r else i + 0.5)
            cy = r if j < r else (n - r if j >= n - r else j + 0.5)
            inside = (i + 0.5 - cx) ** 2 + (j + 0.5 - cy) ** 2 <= r * r + 0.3
            pr, pg, pb, pa = q.getpixel((i, j))
            row.append(f"#{pr:02x}{pg:02x}{pb:02x}" if inside and pa > 96 else None)
        rows.append(row)
    return rows


def load_stats(args):
    cache = os.path.join(DATA, "stats.json")
    token = os.environ.get("GITHUB_TOKEN")
    if token and not args.offline:
        try:
            q = """query($login:String!){ user(login:$login){
              followers{totalCount}
              contributionsCollection{contributionCalendar{totalContributions}}
              repositories(ownerAffiliations:OWNER, privacy:PUBLIC, first:100,
                           orderBy:{field:PUSHED_AT,direction:DESC}){
                totalCount
                nodes{ isFork stargazerCount
                  languages(first:10, orderBy:{field:SIZE,direction:DESC}){
                    edges{ size node{ name color } } } } } } }"""
            body = json.dumps({"query": q, "variables": {"login": USER}}).encode()
            req = urllib.request.Request(
                "https://api.github.com/graphql", data=body,
                headers={"Authorization": f"bearer {token}", "User-Agent": USER})
            u = json.load(urllib.request.urlopen(req, timeout=30))["data"]["user"]
            langs, colors = {}, {}
            for repo in u["repositories"]["nodes"]:
                if repo["isFork"]:
                    continue
                for e in repo["languages"]["edges"]:
                    langs[e["node"]["name"]] = langs.get(e["node"]["name"], 0) + e["size"]
                    colors[e["node"]["name"]] = e["node"]["color"] or "#8b949e"
            total = sum(langs.values()) or 1
            top = sorted(langs.items(), key=lambda kv: -kv[1])[:6]
            stats = {
                "repos": u["repositories"]["totalCount"],
                "stars": sum(r["stargazerCount"] for r in u["repositories"]["nodes"]),
                "followers": u["followers"]["totalCount"],
                "contributions": u["contributionsCollection"]["contributionCalendar"]["totalContributions"],
                "languages": [{"name": k, "pct": v / total, "color": colors[k]} for k, v in top],
                "updated": dt.date.today().isoformat(),
            }
            json.dump(stats, open(cache, "w"), indent=2)
            return stats
        except Exception as e:  # noqa: BLE001
            print("! GitHub API failed, using cache:", e)
    return json.load(open(cache))


# ---------------------------------------------------------------- pieces
HOUSE = [
    "..........mm....cc......",
    "..........mm....cc......",
    "..........rr....cc......",
    ".........rRRr...cc......",
    "........rRRRRr..cc......",
    ".......rRRggRRr.cc......",
    "......rRRRggRRRrcc......",
    ".....rRRRRRRRRRRRr......",
    "....rRRRRRRRRRRRRRr.....",
    "...rrrrrrrrrrrrrrrrr....",
    "....wwwwwwwwwwwwwww.....",
    "....wkkkwwwwwwkkkww.....",
    "....wkkkwwwwwwkkkww.....",
    "....wkkkwwwwwwkkkww.....",
    "....wwwwwwddddwwwww.....",
    "....wwwwwwddddwwwww.....",
    "....WWWWWWddddWWWWW.....",
]
TREE = [
    "..ll..",
    ".lLLl.",
    "lLLLLl",
    "lLLlLl",
    ".lLLl.",
    "..tt..",
    "..tt..",
]
COIN = [
    "..yyyy..",
    ".yYYYYy.",
    "yYyyyYYy",
    "yYyYYYYy",
    "yYyYYYYy",
    "yYyyyYYy",
    ".yYYYYy.",
    "..yyyy..",
]


def hero(theme, counts):
    s = SVG(900, 300, theme, "Léon van der Linden · iOS & Homey developer")
    t = s.t
    s.defs.append(f'<pattern id="dots" width="16" height="16" patternUnits="userSpaceOnUse">'
                  f'<rect x="7" y="7" width="2" height="2" fill="{t["faint"]}"/></pattern>')
    s.window(0, 0, 892, 292, "leon@lrvdlinden: ~")
    s.rect(8, 40, 876, 244, "url(#dots)")
    s.css.append(
        BLINK +
        "@keyframes type{from{transform:translateX(0)}99%%{opacity:1}to{transform:translateX(%dpx);opacity:0}}"
        ".type{animation:type 2.6s steps(%d) .4s forwards}"
        "@keyframes cur{from{transform:translateX(0)}to{transform:translateX(%dpx)}}"
        ".cur{animation:cur 2.6s steps(%d) .4s forwards, blink 1.1s steps(1) 3s infinite}"
        "@keyframes tw{0%%,100%%{opacity:.15}50%%{opacity:1}}"
        ".tw{animation:tw 2.4s ease-in-out infinite}"
        "@keyframes lamp{0%%,45%%{opacity:0}50%%,100%%{opacity:1}}"
        ".l1{animation:lamp 3.2s steps(1) infinite}"
        ".l2{animation:lamp 3.2s steps(1) 1.6s infinite}"
        "@keyframes smoke{0%%{transform:translate(0,0);opacity:0}15%%{opacity:.9}"
        "100%%{transform:translate(14px,-46px);opacity:0}}"
        ".sm{animation:smoke 3s linear infinite}"
        % (int(text_width(TAGLINE, "vt", 30)), len(TAGLINE),
           int(text_width(TAGLINE, "vt", 30)) - 12, len(TAGLINE)))
    # stars
    for i, (x, y) in enumerate([(612, 70), (700, 58), (790, 80), (850, 62), (650, 120),
                                (868, 128), (560, 64), (742, 100)]):
        s.rect(x, y, 4, 4, ["yellow", "blue", "pink", "text"][i % 4], "tw",
               f' style="animation-delay:{i * 0.37:.2f}s"')
    # name — arcade style with a hard offset shadow
    s.text(44, 128, "LÉON", "px", 56, "red")
    s.text(40, 124, "LÉON", "px", 56, "text")
    s.text(42, 166, "VAN DER LINDEN", "px", 22, "blue")
    # typed tagline
    s.text(42, 214, TAGLINE, "vt", 30, "green")
    tw = text_width(TAGLINE, "vt", 30)
    s.rect(40, 190, tw + 8, 34, "panel", "type")
    s.rect(42, 192, 12, 26, "green", "cur")
    # status chips
    x = 42
    for key in ("live", "beta", "dev"):
        label, col = STATUS[key]
        txt = f"{counts.get(key, 0)} {label}"
        w = text_width(txt, "px", 10) + 34
        s.box(x, 242, w, 28, "panel", col, 2, shadow=False)
        s.rect(x + 10, 251, 8, 8, col, "blink" if key == "live" else None)
        s.text(x + 24, 261, txt, "px", 10, col)
        x += w + 12
    # pixel house: the smart home
    hx, hy, px = 612, 128, 8
    pal = dict(r="roof2", R="roof", c="wall2", g="glass", w="wall", W="wall2",
               k="win", d="door", m="dim")
    rows = [row.replace("m", ".") for row in HOUSE]
    s.sprite(rows, pal, hx, hy, px)
    for i in range(3):  # chimney smoke
        s.rect(hx + 16 * px + 2, hy - 6, 10, 10, "dim", "sm",
               f' style="animation-delay:{i}s"')
    # windows that switch on/off like a Homey flow
    s.rect(hx + 5 * px, hy + 11 * px, 3 * px, 3 * px, "glass", "l1")
    s.rect(hx + 14 * px, hy + 11 * px, 3 * px, 3 * px, "glass", "l2")
    s.rect(hx + 12 * px, hy + 15 * px, px, px, "yellow")  # door knob
    s.sprite(TREE, dict(l="leaf2", L="leaf", t="trunk"), hx + 196, hy + 80, 8)
    s.rect(hx - 40, hy + 17 * px, 300, 8, "grass")
    s.rect(hx - 40, hy + 17 * px + 8, 300, 8, "dirt")
    return s.render()


def whoami(theme, counts):
    lines = whoami_lines(counts)
    h = 64 + len(lines) * 26 + 20
    s = SVG(900, h, theme, "whoami — about Léon")
    s.window(0, 0, 892, h - 8, "~/about — zsh")
    s.css.append(BLINK + "@keyframes show{to{opacity:1}}"
                 ".ln{opacity:0;animation:show .01s linear forwards}")
    y = 76
    for i, (kind, val) in enumerate(lines):
        g = f'<g class="ln" style="animation-delay:{0.3 + i * 0.28:.2f}s">'
        s.raw(g)
        if kind in ("cmd", "prompt"):
            s.text(32, y, "leon@nl", "vt", 24, "green")
            s.text(32 + text_width("leon@nl ", "vt", 24), y, "~ $", "vt", 24, "blue")
            x = 32 + text_width("leon@nl ~ $ ", "vt", 24)
            if kind == "cmd":
                s.text(x, y, val, "vt", 24, "text")
            else:
                s.rect(x, y - 18, 11, 22, "text", "blink")
        elif kind == "stat":
            x = 32
            for key in ("live", "beta", "dev"):
                label, col = STATUS[key]
                txt = f"{val.get(key, 0)} {label.lower()}"
                s.rect(x, y - 13, 10, 10, col)
                s.text(x + 18, y, txt, "vt", 24, col)
                x += 18 + text_width(txt, "vt", 24) + 28
            s.text(x, y, f"· {sum(val.values())} apps in total", "vt", 24, "dim")
        elif kind == "dir":
            s.text(32, y, val, "vt", 24, "blue")
        else:
            s.text(32, y, val, "vt", 24, "yellow" if val.startswith("»") else "dim")
        s.raw("</g>")
        y += 26
    return s.render()


def header(theme, cmd, note=""):
    s = SVG(900, 56, theme, cmd)
    s.css.append(BLINK)
    s.rect(0, 26, 16, 4, "line")
    s.text(24, 36, cmd, "px", 16, "text")
    w = 24 + text_width(cmd, "px", 16) + 8
    s.rect(w, 20, 14, 16, "green", "blink")
    if note:
        s.text(896, 36, note, "vt", 22, "dim", "end")
    s.rect(0, 50, 900, 2, "faint")
    return s.render()


def wrap(text, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + (1 if cur else 0) <= width:
            cur = f"{cur} {w}".strip()
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def card(theme, app, icon_rows):
    s = SVG(440, 148, theme, f"{app['name']} — {app['subtitle_en']}")
    s.css.append(BLINK)
    st_label, st_col = STATUS.get(app["status"], ("LIVE", "green"))
    s.box(0, 0, 432, 140, "panel", "line", 4)
    # icon tile
    s.rect(18, 18, 104, 104, "bar")
    if icon_rows:
        s.sprite(icon_rows, None, 22, 22, 6)
    else:
        s.text(70, 84, app["name"][:1].upper(), "px", 40, "blue", "middle")
    # badge
    bw = text_width(st_label, "px", 8) + 28
    bx = 432 - 16 - bw
    s.box(bx, 14, bw, 22, "panel", st_col, 2, shadow=False)
    s.rect(bx + 8, 22, 6, 6, st_col, "blink" if app["status"] == "live" else None)
    s.text(bx + 19, 30, st_label, "px", 8, st_col)
    # texts
    name = app["name"]
    s.text(138, 38, name, "px", 15 if len(name) <= 10 else 12, "text")
    sub, room = app["subtitle_en"], int((432 - 18 - 138) / (0.4 * 22))
    if len(sub) > room:
        sub = sub[:room - 1].rstrip(" ,.") + "…"
    s.text(138, 62, sub, "vt", 22, "blue")
    for i, ln in enumerate(app["desc_lines"]):
        s.text(138, 84 + i * 18, ln, "vt", 19, "dim")
    s.text(138, 126, app["platforms_txt"], "vt", 18, "green")
    return s.render()


def shelf(theme, title, note, apps, icons):
    per_row, tw, th = 8, 107, 112
    rows = (len(apps) + per_row - 1) // per_row
    h = 64 + rows * th + 20
    s = SVG(900, h, theme, title)
    s.window(0, 0, 892, h - 8, title)
    s.text(872, 30, note, "vt", 20, "green", "end")
    for k, app in enumerate(apps):
        r, c = divmod(k, per_row)
        x = 18 + c * tw
        y = 56 + r * th
        s.rect(x + 18, y + 4, 72, 72, "bar")
        if icons.get(app["id"]):
            s.sprite(icons[app["id"]], None, x + 22, y + 8, 4)
        name = app["name"] if len(app["name"]) <= 13 else app["name"][:12] + "…"
        s.text(x + 54, y + 96, name, "vt", 20, "text", "middle")
    return s.render()


def stack(theme):
    s = SVG(900, 10, theme, "Tech stack")
    x, y, rowh = 0, 4, 44
    for name, col in STACK:
        w = text_width(name, "px", 10) + 40
        if x + w > 892:
            x, y = 0, y + rowh
        s.box(x, y, w, 32, "panel", col, 2)
        s.rect(x + 10, y + 12, 8, 8, col)
        s.text(x + 26, y + 21, name, "px", 10, "text")
        x += w + 12
    s.h = y + rowh
    return s.render()


def stats_svg(theme, st):
    s = SVG(900, 220, theme, "GitHub stats")
    s.window(0, 0, 892, 212, "~/stats --live")
    s.text(872, 30, f"updated {st.get('updated', '—')}", "vt", 20, "dim", "end")
    tiles = [("REPOS", st.get("repos"), "blue"), ("STARS", st.get("stars"), "yellow"),
             ("FOLLOWERS", st.get("followers"), "pink"),
             ("CONTRIBS '" + dt.date.today().strftime("%y"), st.get("contributions"), "green")]
    for i, (label, val, col) in enumerate(tiles):
        x = 28 + i * 214
        s.text(x, 92, "—" if val is None else f"{val:,}".replace(",", "."), "px", 26, col)
        s.text(x, 118, label, "vt", 22, "dim")
    # language bar made of pixel blocks
    langs = st.get("languages") or []
    n, bx, by, bwid = 52, 28, 140, 16
    blocks = []
    for lg in langs:
        blocks += [lg["color"]] * max(1, round(lg["pct"] * n))
    blocks = (blocks + ["faint"] * n)[:n]
    for i, col in enumerate(blocks):
        s.rect(bx + i * bwid, by, bwid - 2, 14, col)
    x = 28
    if not langs:
        s.text(x, 184, "languages appear after the first workflow run", "vt", 20, "dim")
    for lg in langs:
        txt = f"{lg['name']} {lg['pct'] * 100:.0f}%"
        if x + text_width(txt, "vt", 20) + 20 > 880:
            break
        s.rect(x, 172, 10, 10, lg["color"])
        s.text(x + 16, 184, txt, "vt", 20, "text")
        x += 16 + text_width(txt, "vt", 20) + 22
    return s.render()


def footer(theme):
    s = SVG(900, 120, theme, "Insert coin — support my apps")
    s.css.append(BLINK + "@keyframes spin{0%,100%{transform:scaleX(1)}50%{transform:scaleX(.15)}}"
                 ".coin{animation:spin 1.4s steps(6) infinite;transform-box:fill-box;transform-origin:center}")
    s.box(0, 0, 892, 112, "panel", "line")
    s.sprite(COIN, dict(y="orange", Y="yellow"), 40, 32, 6, "coin")
    s.sprite(COIN, dict(y="orange", Y="yellow"), 804, 32, 6, "coin")
    s.text(446, 50, "THANKS FOR STOPPING BY", "px", 16, "text", "middle")
    s.text(446, 84, "INSERT COIN  »  LRVDLINDEN.APP/DONATE", "px", 11, "yellow",
           "middle", "blink")
    return s.render()


# ---------------------------------------------------------------- build
PLAT_SHORT = {"Apple TV": "TV", "Apple Watch": "Watch", "Android TV": "Android TV",
              "Samsung TV": "Samsung TV"}


def platforms_txt(pl, limit=40):
    out = ""
    for i, p in enumerate(pl):
        cand = (out + " · " if out else "") + p
        rest = len(pl) - i - 1
        if len(cand) + (6 if rest else 0) > limit:
            return f"{out} · +{len(pl) - i}"
        out = cand
    return out


def app_link(app):
    links = app.get("links") or {}
    if isinstance(links, list):
        links = {}
    for k in ("appstore", "testflight", "website", "homey"):
        if links.get(k):
            return links[k]
    return LINKS["site"]


def pic(name, alt, width=None, href=None):
    w = f' width="{width}"' if width else ""
    p = (f'<picture><source media="(prefers-color-scheme: dark)" srcset="assets/{name}-dark.svg">'
         f'<img alt="{html.escape(alt)}" src="assets/{name}-light.svg"{w}></picture>')
    return f'<a href="{href}">{p}</a>' if href else p


def write(name, theme, svg):
    with open(os.path.join(ASSETS, f"{name}-{theme}.svg"), "w", encoding="utf-8") as f:
        f.write(svg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apps", help="local apps.json instead of the live site")
    ap.add_argument("--img-dir", help="local folder with the app icons")
    ap.add_argument("--offline", action="store_true", help="only use cached data")
    args = ap.parse_args()
    os.makedirs(ASSETS, exist_ok=True)

    apps = [a for a in load_apps(args) if a.get("status") in STATUS]
    counts = {k: sum(1 for a in apps if a["status"] == k) for k in STATUS}

    def en(v):
        return (v.get("en") or v.get("nl") or "") if isinstance(v, dict) else (v or "")

    order = {"live": 0, "beta": 1, "dev": 2}
    ios = [a for a in apps if a.get("section") == "ios"]
    featured = [a for a in ios if a.get("featured") or a.get("subtitle")]
    featured.sort(key=lambda a: (order[a["status"]], not a.get("featured")))
    classics = [a for a in ios if a not in featured]
    homey = [a for a in apps if a.get("section") == "homey"]

    icons = {}
    for a in apps:
        p = load_icon(a, args)
        if p:
            try:
                icons[a["id"]] = pixelate(p)
            except Exception as e:  # noqa: BLE001
                print("! icon failed", a["id"], e)

    stats = load_stats(args)

    # clean old generated cards
    for f in os.listdir(ASSETS):
        if f.startswith("app-"):
            os.remove(os.path.join(ASSETS, f))

    for th in THEMES:
        write("hero", th, hero(th, counts))
        write("whoami", th, whoami(th, counts))
        write("h-apps", th, header(th, "> LS ~/APPS", f"{len(featured)} featured · newest first"))
        write("h-homey", th, header(th, "> LS ~/HOMEY", f"{len(homey)} apps for Homey Pro"))
        write("h-stack", th, header(th, "> CAT STACK.TXT"))
        write("h-stats", th, header(th, "> GIT LOG --STATS"))
        write("homey", th, shelf(th, "~/homey-apps", f"{len(homey)} live", homey, icons))
        if classics:
            write("classics", th, shelf(th, "~/app-store/more", f"{len(classics)} more on the App Store",
                                        classics, icons))
        write("stack", th, stack(th))
        write("stats", th, stats_svg(th, stats))
        write("footer", th, footer(th))
        for a in featured:
            desc = en(a.get("description"))
            lines = wrap(desc, 36)
            if len(lines) > 2:
                lines = lines[:2]
                lines[1] = lines[1][:33].rstrip(" ,.:;") + "…"
            data = dict(a, subtitle_en=en(a.get("subtitle")) or a.get("category", "").title(),
                        desc_lines=lines, platforms_txt=platforms_txt(a.get("platforms", [])))
            write(f"app-{a['id']}", th, card(th, data, icons.get(a["id"])))

    cards = "\n".join(pic(f"app-{a['id']}", f"{a['name']} — {en(a.get('subtitle'))}", "49%", app_link(a))
                      for a in featured)
    readme = f"""<!-- Generated by scripts/build.py — edit the script or data/, not this file. -->
<div align="center">

{pic("hero", "Léon van der Linden — apps for iPhone, Apple TV, Android & Homey", "100%", LINKS["site"])}

{pic("whoami", "whoami — native Apple apps, Homey apps, Android/Windows/TV builds, websites and admin dashboards", "100%")}

{pic("h-apps", "ls ~/apps", "100%")}

{cards}

{pic("classics", "More apps on the App Store", "100%", LINKS["appstore"]) if classics else ""}

{pic("h-homey", "ls ~/homey", "100%")}

{pic("homey", "Homey apps by Léon van der Linden", "100%", LINKS["homey_me"])}

<sub>Homey App Store: <a href="{LINKS["homey_me"]}">Léon van der Linden</a> · <a href="{LINKS["homey_pf"]}">PixelForges</a> · <a href="{LINKS["community"]}">Community topic</a></sub>

{pic("h-stack", "cat stack.txt", "100%")}

{pic("stack", "Swift, SwiftUI, SwiftData, CloudKit, Kotlin, JavaScript, Node.js, Homey SDK 3, HTML/CSS, PHP, GitHub Actions", "100%")}

{pic("h-stats", "git log --stats", "100%")}

{pic("stats", "GitHub stats", "100%")}

<picture><source media="(prefers-color-scheme: dark)" srcset="{RAW}/output/github-snake-dark.svg"><img alt="contribution snake" src="{RAW}/output/github-snake.svg" width="100%"></picture>

{pic("footer", "Insert coin — support my apps", "100%", LINKS["donate"])}

<sub><a href="{LINKS["site"]}">lrvdlinden.app</a> · <a href="{LINKS["appstore"]}">App Store</a> · <a href="{LINKS["homey_me"]}">Homey</a> · <a href="{LINKS["donate"]}">Donate</a></sub>

</div>
"""
    with open(os.path.join(ROOT, "README.md"), "w", encoding="utf-8") as f:
        f.write(readme)
    print(f"built {len(featured)} cards, {len(homey)} homey, {len(classics)} classics; counts {counts}")


if __name__ == "__main__":
    main()
