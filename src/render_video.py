"""
Builds the final 1080x1920, 5-second YouTube Short:

  [ TOP IMAGE   - subtle Ken Burns zoom/pan animation ]   <- watermark text overlaid
  [ WHITE STRIP - bold black Hindi title + summary   ]
  [ BOTTOM IMAGE- subtle Ken Burns zoom/pan animation ]   <- watermark text overlaid

Background music: a random royalty-free track from /music, trimmed to 5s
starting at a random point.
"""

import os
import random
import textwrap
import requests
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (
    ImageClip, CompositeVideoClip, AudioFileClip, concatenate_videoclips
)

W, H = 1080, 1920
DURATION = 5
TOP_H = 700
BOTTOM_H = 700
MID_H = H - TOP_H - BOTTOM_H  # 520

FONT_URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/notosansdevanagari/NotoSansDevanagari%5Bwdth%2Cwght%5D.ttf"
FONT_DIR = os.path.join(os.path.dirname(__file__), "..", "assets")
FONT_PATH = os.path.join(FONT_DIR, "NotoSansDevanagari-Bold.ttf")


def ensure_font():
    os.makedirs(FONT_DIR, exist_ok=True)
    if not os.path.exists(FONT_PATH):
        r = requests.get(FONT_URL, timeout=60)
        r.raise_for_status()
        with open(FONT_PATH, "wb") as f:
            f.write(r.content)
    return FONT_PATH


def _wrapped_text_image(text, font_path, font_size, max_width, fill, bg=None):
    font = ImageFont.truetype(font_path, font_size)
    dummy = Image.new("RGB", (10, 10))
    draw = ImageDraw.Draw(dummy)

    # wrap text so each line fits max_width
    words = text.split()
    lines, current = [], ""
    for w in words:
        trial = (current + " " + w).strip()
        bbox = draw.textbbox((0, 0), trial, font=font)
        if bbox[2] - bbox[0] <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = w
    if current:
        lines.append(current)

    line_height = int(font_size * 1.25)
    img_h = line_height * len(lines) + 20
    img = Image.new("RGBA", (max_width, img_h), bg if bg else (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    y = 10
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_w = bbox[2] - bbox[0]
        x = (max_width - line_w) // 2
        draw.text((x, y), line, font=font, fill=fill)
        y += line_height
    return img


def make_middle_panel(title, summary, font_path):
    """White strip with bold black title + summary, centered."""
    panel = Image.new("RGB", (W, MID_H), "white")

    title_img = _wrapped_text_image(title, font_path, 62, W - 100, fill="black")
    summary_img = _wrapped_text_image(summary, font_path, 38, W - 140, fill=(40, 40, 40))

    total_h = title_img.height + summary_img.height + 30
    start_y = max(10, (MID_H - total_h) // 2)

    panel.paste(title_img, ((W - title_img.width) // 2, start_y), title_img)
    panel.paste(summary_img, ((W - summary_img.width) // 2, start_y + title_img.height + 30), summary_img)
    return panel


def make_watermark(text, font_path, size=34):
    font = ImageFont.truetype(font_path, size)
    dummy = Image.new("RGBA", (10, 10))
    d = ImageDraw.Draw(dummy)
    bbox = d.textbbox((0, 0), text, font=font)
    w, h = bbox[2] - bbox[0] + 40, bbox[3] - bbox[1] + 24
    img = Image.new("RGBA", (w, h), (0, 0, 0, 110))  # semi-transparent black pill
    d = ImageDraw.Draw(img)
    d.text((20, 8), text, font=font, fill="white")
    return img


def _kenburns_clip(image_path, target_w, target_h, duration, zoom_in=True):
    """Simple Ken Burns: slow zoom + slight pan, resized to exactly fill target box."""
    clip = ImageClip(image_path)

    # scale image to cover target box first
    scale = max(target_w / clip.w, target_h / clip.h) * 1.15  # extra 15% for zoom headroom
    clip = clip.resize(scale)

    def zoom(t):
        progress = t / duration
        factor = (1.0 + 0.08 * progress) if zoom_in else (1.08 - 0.08 * progress)
        return factor

    clip = clip.resize(lambda t: zoom(t))
    clip = clip.set_position(("center", "center")).set_duration(duration)
    return clip


def render_short(top_image_path, bottom_image_path, title, summary,
                  music_path, channel_name, out_path):
    font_path = ensure_font()

    # ---- Middle white text panel ----
    mid_img = make_middle_panel(title, summary, font_path)
    mid_path = "/tmp/_mid_panel.png"
    mid_img.save(mid_path)
    mid_clip = ImageClip(mid_path).set_duration(DURATION).set_position((0, TOP_H))

    # ---- Top & bottom animated image panels (cropped into their boxes) ----
    top_bg = CompositeVideoClip(
        [_kenburns_clip(top_image_path, W, TOP_H, DURATION, zoom_in=True)],
        size=(W, TOP_H)
    ).set_duration(DURATION).set_position((0, 0))

    bottom_bg = CompositeVideoClip(
        [_kenburns_clip(bottom_image_path, W, BOTTOM_H, DURATION, zoom_in=False)],
        size=(W, BOTTOM_H)
    ).set_duration(DURATION).set_position((0, H - BOTTOM_H))

    # ---- Watermarks ----
    wm_img = make_watermark(channel_name, font_path)
    wm_path = "/tmp/_watermark.png"
    wm_img.save(wm_path)

    wm_top = (ImageClip(wm_path)
              .set_duration(DURATION)
              .set_position(("center", 30)))
    wm_bottom = (ImageClip(wm_path)
                 .set_duration(DURATION)
                 .set_position(("center", H - wm_img.height - 30)))

    # ---- Compose everything ----
    final = CompositeVideoClip(
        [top_bg, bottom_bg, mid_clip, wm_top, wm_bottom],
        size=(W, H)
    ).set_duration(DURATION)

    # ---- Background music: random 5s slice ----
    if music_path and os.path.exists(music_path):
        audio = AudioFileClip(music_path)
        if audio.duration > DURATION:
            start = random.uniform(0, audio.duration - DURATION)
            audio = audio.subclip(start, start + DURATION)
        else:
            audio = audio.audio_loop(duration=DURATION) if hasattr(audio, "audio_loop") else audio
        final = final.set_audio(audio)

    final.write_videofile(
        out_path, fps=30, codec="libx264", audio_codec="aac",
        preset="medium", threads=4, logger=None
    )
    return out_path


def pick_random_music():
    music_dir = os.path.join(os.path.dirname(__file__), "..", "music")
    tracks = [f for f in os.listdir(music_dir)
              if f.lower().endswith((".mp3", ".wav", ".m4a"))] if os.path.exists(music_dir) else []
    if not tracks:
        return None
    return os.path.join(music_dir, random.choice(tracks))
