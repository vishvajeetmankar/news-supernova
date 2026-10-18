"""Studio render: modern news layout, 1080x1920. Scene A = anchor bada (intro), Scene B = story visuals + anchor kone me."""
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import VideoClip, ImageClip, AudioFileClip, CompositeVideoClip, ColorClip, vfx
from . import anchor as A

W, H, FPS = 1080, 1920, 25
RED, RED2, YEL = (214, 18, 34), (150, 8, 24), (255, 214, 10)
HEADER, BAND_BOTTOM, CAP_BOTTOM = 150, 1560, 1830

# ---------------- text helpers ----------------
def font(size, latin=False):
    if os.getenv("FONT_PATH") and not latin: return ImageFont.truetype(os.environ["FONT_PATH"], size)
    pats = ["DejaVuSans-Bold.ttf"] if latin else ["NotoSansDevanagari-Bold.ttf", "NotoSansDevanagari*.ttf", "*Devanagari*.ttf"]
    for pat in pats:
        for p in Path("/usr/share/fonts").rglob(pat): return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()

def wrap(d, text, f, maxw):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= maxw: cur = t
        else: lines.append(cur); cur = w
    return lines + [cur] if cur else lines

def txt(d, xy, s, f, fill, sw=2):
    d.text(xy, s, font=f, fill=fill, stroke_width=sw, stroke_fill=(0, 0, 0, 255))

def rmask(w, h, r):
    m = Image.new("L", (w * 2, h * 2), 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, w * 2 - 1, h * 2 - 1], radius=r * 2, fill=255)
    return np.array(m.resize((w, h), Image.LANCZOS)).astype("float32") / 255.0

# ---------------- background / overlays ----------------
def backdrop():
    y = np.linspace(0, 1, H, dtype="float32")[:, None, None]
    base = np.array((4, 8, 24), "float32") * (1 - y) + np.array((8, 20, 56), "float32") * y
    base = np.broadcast_to(base, (H, W, 3)).copy()
    glow = np.zeros((H // 4, W // 4, 3), "float32")
    for (cx, cy, rad, col) in ((120, 520, 430, (40, 110, 255)), (950, 1250, 460, (255, 40, 70)), (540, 120, 380, (30, 70, 200))):
        cv2.circle(glow, (cx // 4, cy // 4), rad // 4, col, -1)
    glow = cv2.GaussianBlur(glow, (0, 0), 55) * 0.55
    base += cv2.resize(glow, (W, H), interpolation=cv2.INTER_CUBIC)
    g = np.zeros((H, W), "float32")                                   # subtle perspective-less tech grid
    g[::90, :] = 1; g[:, ::90] = 1; base += (cv2.GaussianBlur(g, (0, 0), 0.8) * 9)[..., None]
    yy, xx = np.mgrid[0:H, 0:W].astype("float32")
    vig = 1 - 0.55 * (((xx - W / 2) / (W * 0.75)) ** 2 + ((yy - H / 2) / (H * 0.7)) ** 2)
    return np.clip(base * np.clip(vig, 0.35, 1)[..., None], 0, 255).astype("uint8")

def ist_date():
    return datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime("%d %b %Y").upper()

def base_overlay(headline):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, HEADER], fill=(4, 8, 22, 246)); d.rectangle([0, HEADER - 4, W, HEADER], fill=RED + (255,))
    d.rectangle([28, 30, 612, 118], fill=RED + (255,)); d.polygon([(612, 30), (650, 30), (612, 118)], fill=RED + (255,))
    txt(d, (50, 46), "NEWS SUPERNOVA", font(48, True), (255, 255, 255, 255))
    d.rounded_rectangle([W - 330, 40, W - 28, 108], radius=34, outline=(255, 255, 255, 120), width=2, fill=(255, 255, 255, 22))
    d.text((W - 305, 55), ist_date(), font=font(34, True), fill=(255, 255, 255, 255))
    hf = font(60); lines = wrap(d, headline, hf, W - 100)[:3]
    y0 = BAND_BOTTOM - (46 + 76 * len(lines))
    band = np.zeros((BAND_BOTTOM - y0, W, 4), "float32")
    band[..., :3] = np.linspace(RED, RED2, W, dtype="float32")[None, :, :]; band[..., 3] = 250
    im.alpha_composite(Image.fromarray(band.astype("uint8"), "RGBA"), (0, y0))
    d.rectangle([0, y0 - 7, W, y0], fill=YEL + (255,))
    for i, l in enumerate(lines): txt(d, (48, y0 + 22 + 76 * i), l, hf, (255, 255, 255, 255))
    d.rectangle([0, BAND_BOTTOM, W, CAP_BOTTOM], fill=(6, 10, 26, 246))
    d.rectangle([0, CAP_BOTTOM, W, H], fill=(255, 255, 255, 255))
    return np.array(im), y0

def top_overlay():
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rectangle([0, CAP_BOTTOM, 200, H], fill=RED + (255,)); txt(d, (20, 1858), "UPDATES", font(34, True), (255, 255, 255, 255))
    return np.array(im)

def badge(text):
    im = Image.new("RGBA", (420, 70), YEL + (255,)); ImageDraw.Draw(im).text((22, 12), text, font=font(40, True), fill=(140, 0, 10, 255))
    return np.array(im)

def frame_glow(w, h, r):
    """Video-wall ka border + glow (static RGBA)."""
    pad = 24; im = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([pad, pad, pad + w, pad + h], radius=r, outline=(70, 140, 255, 255), width=6)
    glow = im.filter(__import__("PIL.ImageFilter", fromlist=["x"]).GaussianBlur(10)); glow.alpha_composite(im)
    d2 = ImageDraw.Draw(glow); d2.rounded_rectangle([pad, pad, pad + w, pad + h], radius=r, outline=(255, 255, 255, 210), width=2)
    return np.array(glow), pad

def cap_img(text):
    im = Image.new("RGBA", (W, 270), (0, 0, 0, 0)); d = ImageDraw.Draw(im); f = font(62)
    lines = wrap(d, text, f, W - 80)[:2]; y = (270 - 76 * len(lines)) // 2
    for l in lines:
        txt(d, ((W - d.textlength(l, font=f)) / 2, y), l, f, YEL + (255,)); y += 76
    return np.array(im)

def ticker_img(items, dur):
    f = font(40); s = "   |   ".join(map(str, items)) + "   |   "
    w1 = int(ImageDraw.Draw(Image.new("RGBA", (1, 1))).textlength(s, font=f)) + 1
    reps = int((W + 200 + dur * 170) // w1) + 2
    im = Image.new("RGBA", (w1 * reps, 90), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    for i in range(reps): d.text((i * w1, 16), s, font=f, fill=(10, 10, 30, 255))
    return np.array(im)

# ---------------- story visuals ----------------
def zfn(path, dur, size, z=0.12):   # Ken Burns, manual PIL frames
    tw, th = size; im = Image.open(path).convert("RGB")
    s = max(tw / im.width, th / im.height) * (1 + z)
    base = im.resize((int(im.width * s) + 2, int(im.height * s) + 2), Image.LANCZOS); bw, bh = base.size
    def mk(t):
        k = 1 + z - z * min(t / max(dur, .01), 1); ww, wh = tw * k, th * k; x, y = (bw - ww) / 2, (bh - wh) / 2
        return np.array(base.resize((tw, th), Image.BILINEAR, box=(x, y, x + ww, y + wh)))
    return mk

def broll(paths, dur, size):
    n = len(paths); per = dur / n; fns = [zfn(p, per + 0.4, size) for p in paths]
    def mk(t):
        i = min(int(t / per), n - 1); lt = t - i * per; f = fns[i](lt)
        if i > 0 and lt < 0.35:
            a = lt / 0.35; f = (fns[i - 1](per + lt) * (1 - a) + f * a).astype("uint8")
        return f
    return VideoClip(mk, duration=dur)

def rounded(clip, w, h, r, dur):
    return clip.set_mask(ImageClip(rmask(w, h, r), ismask=True).set_duration(dur))

# ---------------- anchor layers ----------------
def anchor_layer(P, env, t0, dur, out_w, x, y_bottom):
    """Puppet anchor ka clip [t0, t0+dur). Alpha mask + soft shadow ke saath."""
    out_h = int(round(P.h * out_w / P.w)); y = y_bottom - out_h
    sh = A.shadow_alpha(P.camera(P.rgba, 0, 0, out_w))
    cache = {}
    def fr(t):
        g = t0 + t; key = int(round(g * FPS))
        if cache.get("k") != key:
            o = float(env[min(key, len(env) - 1)])
            cam = P.camera(P.frame(g, o), g, o, out_w); rgb, a = A.with_shadow(cam, sh)
            cache.update(k=key, rgb=rgb, a=a)
        return cache
    col = VideoClip(lambda t: fr(t)["rgb"], duration=dur)
    msk = VideoClip(lambda t: fr(t)["a"], ismask=True, duration=dur)
    return col.set_mask(msk).set_position((x, y)).set_start(t0)

def static_anchor_layer(path, t0, dur, out_w, x, y_bottom):   # fallback (mediapipe fail ho to)
    im = Image.open(path).convert("RGBA"); h = int(im.height * out_w / im.width); im = im.resize((out_w, h), Image.LANCZOS); a = np.array(im)
    c = ImageClip(a[:, :, :3]).set_mask(ImageClip(a[:, :, 3] / 255.0, ismask=True))
    return c.set_duration(dur).set_start(t0).set_position((x, y_bottom - h))

def caps(text, t0, dur):
    w = text.split(); cs = [" ".join(w[i:i + 5]) for i in range(0, len(w), 5)]
    tot = sum(len(c) for c in cs); t = t0; out = []
    for c in cs:
        d = dur * len(c) / tot
        out.append(ImageClip(cap_img(c)).set_start(t).set_duration(d).set_position((0, BAND_BOTTOM))); t += d
    return out

# ---------------- build ----------------
def build(d, wavA, wavB, wavAll, mixwav, images, out):
    dA, dB = AudioFileClip(wavA).duration, AudioFileClip(wavB).duration
    T = dA + dB + 0.6
    layers = [ImageClip(backdrop()).set_duration(T)]
    # Scene A: video wall (story) + bada anchor
    ww, wh = 960, 540; wx, wy = 60, HEADER + 30
    wall = rounded(VideoClip(zfn(images[0], dA, (ww, wh)), duration=dA), ww, wh, 26, dA).set_position((wx, wy))
    gl, pad = frame_glow(ww, wh, 26)
    layers += [wall, ImageClip(gl).set_duration(dA).set_position((wx - pad, wy - pad))]
    # Scene B: poori story window
    bw_, bh_ = 1020, 1290; bx, by = 30, HEADER + 25
    bimgs = images[1:] + images[:1] if len(images) > 1 else images
    win = rounded(broll(bimgs, dB, (bw_, bh_)), bw_, bh_, 28, dB).set_start(dA).set_position((bx, by))
    gl2, pad2 = frame_glow(bw_, bh_, 28)
    layers += [win, ImageClip(gl2).set_start(dA).set_duration(dB).set_position((bx - pad2, by - pad2))]
    # Anchor: A me bada (beech me), B me kone me (neeche-daayen) — poori awaaz par lip-sync
    try:
        P = A.Puppet(); env = A.envelope(wavAll)
        layers.append(anchor_layer(P, env, 0, dA, 820, (W - 820) // 2, BAND_BOTTOM))
        layers.append(anchor_layer(P, env, dA, T - dA, 560, W - 560 - 20, BAND_BOTTOM))
    except Exception as e:
        print("[anchor] puppet fail ->", repr(e), "| static anchor")
        layers.append(static_anchor_layer(A.IMG, 0, dA, 820, (W - 820) // 2, BAND_BOTTOM))
        layers.append(static_anchor_layer(A.IMG, dA, T - dA, 560, W - 560 - 20, BAND_BOTTOM))
    # Overlays
    base, y0 = base_overlay(d["headline"])
    layers.append(ImageClip(base).set_duration(T))
    layers.append(ImageClip(ticker_img(d["ticker"], T)).set_duration(T).set_position(lambda t: (W - 170 * t, CAP_BOTTOM)))
    layers.append(ImageClip(top_overlay()).set_duration(T).fx(vfx.fadein, 0.7))
    tag = "BREAKING" if (d["tone"] == "breaking" or "बड़ी" in d.get("opener", "")) else "TRENDING NOW"
    layers.append(ImageClip(badge(tag)).set_start(0.4).set_duration(T - 0.4)
                  .set_position(lambda t: (min(0, -440 + 1600 * t), y0 - 77)))
    layers.append(ColorClip((W, H), color=(255, 255, 255)).set_start(dA).set_duration(0.14).set_opacity(0.55))   # scene-cut flash
    layers += caps(d["anchor_full"], 0, dA) + caps(d["voiceover_full"], dA, dB)
    v = CompositeVideoClip(layers, size=(W, H)).set_duration(T).set_audio(AudioFileClip(mixwav))
    v.write_videofile(str(out), fps=FPS, codec="libx264", audio_codec="aac", preset="veryfast",
                      threads=4, ffmpeg_params=["-pix_fmt", "yuv420p", "-crf", "22"], logger=None)
    return str(out)
