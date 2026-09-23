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
import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from moviepy.editor import (
    ImageClip, CompositeVideoClip, AudioFileClip, VideoClip, concatenate_videoclips
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


def _wrapped_text_image(text, font_path, font_size, max_width, fill, bg=None,
                         stroke_width=0, stroke_fill=None):
    font = ImageFont.truetype(font_path, font_size)
    dummy = Image.new("RGB", (10, 10))
    draw = ImageDraw.Draw(dummy)

    # wrap text so each line fits max_width
    words = text.split()
    lines, current = [], ""
    for w in words:
        trial = (current + " " + w).strip()
        bbox = draw.textbbox((0, 0), trial, font=font, stroke_width=stroke_width)
        if bbox[2] - bbox[0] <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = w
    if current:
        lines.append(current)

    line_height = int(font_size * 1.3)
    img_h = line_height * len(lines) + 20
    img = Image.new("RGBA", (max_width, img_h), bg if bg else (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    y = 10
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font, stroke_width=stroke_width)
        line_w = bbox[2] - bbox[0]
        x = (max_width - line_w) // 2
        draw.text((x, y), line, font=font, fill=fill,
                   stroke_width=stroke_width, stroke_fill=stroke_fill)
        y += line_height
    return img


def make_middle_panel(title, summary, font_path):
    """Off-white strip with BOLD outlined red title + dark summary, centered, with a red divider."""
    title = (title or "आज की बड़ी खबर").strip()
    summary = (summary or "इस खबर से जुड़ी महत्वपूर्ण जानकारी सामने आई है।").strip()

    panel = Image.new("RGB", (W, MID_H), (250, 250, 248))
    draw = ImageDraw.Draw(panel)

    title_img = _wrapped_text_image(
        title, font_path, 70, W - 80, fill=(215, 20, 25),
        stroke_width=3, stroke_fill=(20, 10, 10)
    )
    summary_img = _wrapped_text_image(
        summary, font_path, 40, W - 130, fill=(25, 25, 25),
        stroke_width=1, stroke_fill=(25, 25, 25)
    )

    divider_h = 8
    total_h = title_img.height + divider_h + 24 + summary_img.height
    start_y = max(6, (MID_H - total_h) // 2)

    panel.paste(title_img, ((W - title_img.width) // 2, start_y), title_img)

    divider_y = start_y + title_img.height + 10
    divider_w = 180
    draw.rectangle(
        [(W - divider_w) // 2, divider_y, (W + divider_w) // 2, divider_y + divider_h],
        fill=(200, 16, 24),
    )

    panel.paste(summary_img, ((W - summary_img.width) // 2, divider_y + divider_h + 18), summary_img)
    return panel


def make_breaking_badge(font_path, text="ब्रेकिंग न्यूज़"):
    """Red 'BREAKING NEWS' style ribbon badge, TV-news style."""
    font = ImageFont.truetype(font_path, 44)
    dummy = Image.new("RGBA", (10, 10))
    d = ImageDraw.Draw(dummy)
    bbox = d.textbbox((0, 0), text, font=font, stroke_width=2)
    pad_x, pad_y = 40, 18
    w = bbox[2] - bbox[0] + pad_x * 2
    h = bbox[3] - bbox[1] + pad_y * 2

    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w, h], fill=(215, 15, 15, 255))
    # small white square "on-air" dot for extra news feel
    dot_r = 9
    d.ellipse([pad_x - 28, h // 2 - dot_r, pad_x - 28 + dot_r * 2, h // 2 + dot_r], fill="white")
    d.text((pad_x, pad_y - 6), text, font=font, fill="white",
           stroke_width=2, stroke_fill=(120, 0, 0))
    return img


def make_vignette(w, h, top=True, strength=140):
    """Soft dark gradient at the outer edge of a panel, so overlaid text/badges pop."""
    grad = Image.new("L", (1, h), 0)
    for y in range(h):
        # fade from dark (edge) to transparent (center)
        d = y / h if top else 1 - (y / h)
        alpha = int(strength * max(0, 1 - d * 3))
        grad.putpixel((0, y), alpha)
    grad = grad.resize((w, h))
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    overlay.putalpha(grad)
    black = Image.new("RGBA", (w, h), (0, 0, 0, 255))
    black.putalpha(grad)
    return black


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
        factor = (1.0 + 0.18 * progress) if zoom_in else (1.18 - 0.18 * progress)
        return factor

    clip = clip.resize(lambda t: zoom(t))
    clip = clip.set_position(("center", "center")).set_duration(duration)
    return clip


def _pulsing_border_clip(w, h, duration, thickness=14):
    """Thin red frame around the whole video, pulsing in/out like a news alert."""
    def make_frame(t):
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        frame[:, :, 0] = 210  # red channel
        return frame

    def make_mask(t):
        alpha = 0.35 + 0.55 * (0.5 + 0.5 * np.sin(t * 6))
        mask = np.zeros((h, w), dtype=np.float64)
        mask[:thickness, :] = alpha
        mask[-thickness:, :] = alpha
        mask[:, :thickness] = alpha
        mask[:, -thickness:] = alpha
        return mask

    color_clip = VideoClip(make_frame, duration=duration)
    mask_clip = VideoClip(make_mask, duration=duration, ismask=True)
    return color_clip.set_mask(mask_clip)


def _opening_flash_clip(w, h, flash_duration=0.15):
    """Quick white flash at the very start - a classic 'stop the scroll' hook."""
    def make_frame(t):
        return np.full((h, w, 3), 255, dtype=np.uint8)

    def make_mask(t):
        alpha = max(0.0, 1.0 - (t / flash_duration))
        return np.full((h, w), alpha, dtype=np.float64)

    color_clip = VideoClip(make_frame, duration=flash_duration)
    mask_clip = VideoClip(make_mask, duration=flash_duration, ismask=True)
    return color_clip.set_mask(mask_clip)


def _breathing_clip(image_path, w, h, duration, amp=0.035, freq=2.2):
    """Very subtle pulse/breathing zoom so the text panel feels alive, not static."""
    clip = ImageClip(image_path)
    clip = clip.resize((w, h))

    def scale(t):
        return 1.0 + amp * (0.5 + 0.5 * np.sin(t * freq * 2 * np.pi))

    clip = clip.resize(lambda t: scale(t)).set_position(("center", "center")).set_duration(duration)
    return CompositeVideoClip([clip], size=(w, h)).set_duration(duration)


def render_short(top_image_path, bottom_image_path, title, summary,
                  music_path, channel_name, out_path):
    for path in (top_image_path, bottom_image_path):
        if not os.path.isfile(path) or os.path.getsize(path) == 0:
            raise RuntimeError(f"Invalid image file: {path}")

    title = (title or "आज की बड़ी खबर").strip()
    summary = (summary or "इस खबर से जुड़ी महत्वपूर्ण जानकारी सामने आई है।").strip()

    font_path = ensure_font()

    # ---- Middle white text panel (with a subtle breathing pulse) ----
    mid_img = make_middle_panel(title, summary, font_path)
    mid_path = "/tmp/_mid_panel.png"
    mid_img.save(mid_path)
    mid_clip = _breathing_clip(mid_path, W, MID_H, DURATION).set_position((0, TOP_H))

    # ---- Top & bottom animated image panels (cropped into their boxes) ----
    top_bg = CompositeVideoClip(
        [_kenburns_clip(top_image_path, W, TOP_H, DURATION, zoom_in=True)],
        size=(W, TOP_H)
    ).set_duration(DURATION).set_position((0, 0))

    bottom_bg = CompositeVideoClip(
        [_kenburns_clip(bottom_image_path, W, BOTTOM_H, DURATION, zoom_in=False)],
        size=(W, BOTTOM_H)
    ).set_duration(DURATION).set_position((0, H - BOTTOM_H))

    # ---- Vignettes: soft dark gradient at the outer edge of each image panel ----
    top_vignette_img = make_vignette(W, 120, top=True)
    top_vignette_path = "/tmp/_vignette_top.png"
    top_vignette_img.save(top_vignette_path)
    top_vignette = ImageClip(top_vignette_path).set_duration(DURATION).set_position((0, 0))

    bottom_vignette_img = make_vignette(W, 120, top=False)
    bottom_vignette_path = "/tmp/_vignette_bottom.png"
    bottom_vignette_img.save(bottom_vignette_path)
    bottom_vignette = ImageClip(bottom_vignette_path).set_duration(DURATION).set_position((0, H - 120))

    # ---- Breaking-news style red badge, top-left over the top image ----
    badge_img = make_breaking_badge(font_path)
    badge_path = "/tmp/_badge.png"
    badge_img.save(badge_path)
    badge_clip = ImageClip(badge_path).set_duration(DURATION).set_position((30, 90))

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

    # ---- Pulsing red alert border around the whole frame ----
    border_clip = _pulsing_border_clip(W, H, DURATION)

    # ---- Quick opening flash - grabs attention the instant it appears in feed ----
    flash_clip = _opening_flash_clip(W, H)

    # ---- Compose everything ----
    final = CompositeVideoClip(
        [top_bg, bottom_bg, top_vignette, bottom_vignette, mid_clip,
         badge_clip, wm_top, wm_bottom, border_clip, flash_clip],
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
        preset="medium", threads=2, logger="bar"
    )
    return out_path


def pick_random_music():
    music_dir = os.path.join(os.path.dirname(__file__), "..", "music")
    tracks = [f for f in os.listdir(music_dir)
              if f.lower().endswith((".mp3", ".wav", ".m4a"))] if os.path.exists(music_dir) else []
    if not tracks:
        return None
    return os.path.join(music_dir, random.choice(tracks))
