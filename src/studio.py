from pathlib import Path
import os, random, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (VideoClip, ImageClip, VideoFileClip, AudioFileClip, CompositeAudioClip,
                            CompositeVideoClip, ColorClip, concatenate_audioclips, vfx)
from moviepy.audio.fx.all import volumex, audio_fadeout
from .anchor import IMG

W, H, FPS = 1080, 1920, 25
RED, YEL = (206, 14, 30), (255, 214, 10)
AP = 830; AX, AY = (W - AP) // 2, 730
BAND_BOTTOM = 1560

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

def txt(d, xy, s, f, fill):
    d.text(xy, s, font=f, fill=fill, stroke_width=2, stroke_fill=(0, 0, 0, 255))

def backdrop():
    y = np.linspace(0, 1, H)[:, None, None]
    return ((np.array((8, 16, 40)) * (1 - y) + np.array((2, 4, 12)) * y) * np.ones((H, W, 3))).astype("uint8")

def base_overlay(headline):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 172], fill=(6, 10, 24, 255)); d.rectangle([0, 168, W, 174], fill=RED + (255,))
    hf = font(60); lines = wrap(d, headline, hf, W - 90)[:3]
    y0 = BAND_BOTTOM - (44 + 76 * len(lines))
    d.rectangle([0, y0, W, BAND_BOTTOM], fill=RED + (248,)); d.rectangle([0, y0 - 7, W, y0], fill=YEL + (255,))
    for i, l in enumerate(lines): txt(d, (45, y0 + 20 + 76 * i), l, hf, (255, 255, 255, 255))
    d.rectangle([0, BAND_BOTTOM, W, 1830], fill=(0, 0, 0, 240))
    d.rectangle([0, 1830, W, H], fill=(255, 255, 255, 255))
    return np.array(im), y0

def top_overlay():
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rectangle([30, 32, 590, 138], fill=RED + (255,)); txt(d, (52, 52), "NEWS SUPERNOVA", font(46, True), (255, 255, 255, 255))
    d.rounded_rectangle([W - 290, 46, W - 30, 124], radius=14, fill=(255, 255, 255, 255))
    d.text((W - 268, 62), "AI ANCHOR", font=font(34, True), fill=(10, 10, 30, 255))
    d.rectangle([0, 1830, 200, H], fill=RED + (255,)); txt(d, (18, 1856), "UPDATES", font(34, True), (255, 255, 255, 255))
    return np.array(im)

def badge(text):
    im = Image.new("RGBA", (400, 70), YEL + (255,)); ImageDraw.Draw(im).text((20, 12), text, font=font(40, True), fill=(150, 0, 10, 255))
    return np.array(im)

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

def zfn(path, dur, size, z=0.12, pulse=None):   # Ken Burns, manual PIL frames
    tw, th = size; im = Image.open(path).convert("RGB")
    s = max(tw / im.width, th / im.height) * (1 + z)
    base = im.resize((int(im.width * s) + 2, int(im.height * s) + 2), Image.LANCZOS); bw, bh = base.size
    def mk(t):
        k = 1 + z - z * min(t / max(dur, .01), 1)
        if pulse: k *= 1 - 0.03 * pulse(t)
        ww, wh = tw * k, th * k; x, y = (bw - ww) / 2, (bh - wh) / 2
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

def envelope(wav):   # ffmpeg se seedha padhta hai (moviepy ka to_soundarray numpy>=1.24 pe crash karta hai)
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(wav), "-ac", "1", "-ar", "8000", "-f", "s16le", "-"],
                         capture_output=True).stdout
    a = np.abs(np.frombuffer(raw, dtype=np.int16).astype("float32"))
    r = np.convolve(a, np.ones(400) / 400, "same"); r = r / (r.max() + 1e-9)
    return lambda t: float(r[min(int(t * 8000), len(r) - 1)])

def caps(text, t0, dur):
    w = text.split(); cs = [" ".join(w[i:i + 5]) for i in range(0, len(w), 5)]
    tot = sum(len(c) for c in cs); t = t0; out = []
    for c in cs:
        d = dur * len(c) / tot
        out.append(ImageClip(cap_img(c)).set_start(t).set_duration(d).set_position((0, BAND_BOTTOM))); t += d
    return out

def music_track(T):
    """music/ folder se random track ka random slice (volume dabaa hua, awaaz ke neeche)."""
    d = Path(__file__).resolve().parent.parent / "music"
    tr = [f for f in d.iterdir() if f.suffix.lower() in (".mp3", ".wav", ".m4a")] if d.exists() else []
    if not tr or os.getenv("MUSIC_VOL") == "0": return None
    try:
        m = AudioFileClip(str(random.choice(tr)))
        if m.duration >= T:
            st = random.uniform(0, m.duration - T); m = m.subclip(st, st + T)
        else:
            m = concatenate_audioclips([m] * (int(T // m.duration) + 1)).subclip(0, T)
        return m.fx(volumex, float(os.getenv("MUSIC_VOL", "0.12"))).fx(audio_fadeout, 1.0)
    except Exception as e:
        print("[music] skip:", e); return None

def mix(wav, T):
    voice, m = AudioFileClip(wav), music_track(T)
    return CompositeAudioClip([m, voice]).set_duration(T) if m else voice

def build(d, wavA, wavB, wavAll, anchor_mp4, images, out):
    dA, dB = AudioFileClip(wavA).duration, AudioFileClip(wavB).duration
    T = dA + dB + 0.6
    layers = [ImageClip(backdrop()).set_duration(T)]
    layers.append(VideoClip(zfn(images[0], dA, (W, 560)), duration=dA).set_position((0, 174)))
    layers.append(ColorClip((AP + 8, AP + 8), color=(255, 255, 255)).set_position((AX - 4, AY - 4)).set_duration(dA))
    if anchor_mp4:
        ac = VideoFileClip(anchor_mp4, audio=False).subclip(0, dA)
    else:   # fallback: still anchor, awaaz ke saath pulse
        ac = VideoClip(zfn(str(IMG), dA, (AP, AP), z=0.04, pulse=envelope(wavA)), duration=dA) if IMG.exists() \
            else ColorClip((AP, AP), color=(20, 30, 60)).set_duration(dA)
    layers.append(ac.set_position((AX, AY)))
    layers.append(broll(images, dB, (W, 1386)).set_start(dA).set_position((0, 174)))
    base, y0 = base_overlay(d["headline"])
    layers.append(ImageClip(base).set_duration(T))
    layers.append(ImageClip(ticker_img(d["ticker"], T)).set_duration(T).set_position(lambda t: (W - 170 * t, 1830)))
    layers.append(ImageClip(top_overlay()).set_duration(T).fx(vfx.fadein, 0.7))
    tag = "BREAKING" if (d["tone"] == "breaking" or "बड़ी" in d.get("opener", "")) else "TRENDING NOW"
    layers.append(ImageClip(badge(tag)).set_start(0.4).set_duration(T - 0.4)
                  .set_position(lambda t: (min(0, -420 + 1600 * t), y0 - 77)))
    layers += caps(d["anchor_full"], 0, dA) + caps(d["voiceover_full"], dA, dB)
    v = CompositeVideoClip(layers, size=(W, H)).set_duration(T).set_audio(mix(wavAll, T))
    v.write_videofile(str(out), fps=FPS, codec="libx264", audio_codec="aac", preset="veryfast",
                      threads=4, ffmpeg_params=["-pix_fmt", "yuv420p", "-crf", "23"], logger=None)
    return str(out)
