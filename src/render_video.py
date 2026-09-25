# ============================================================
# FILE: src/render_video.py
# ============================================================
"""
Builds the final 1080x1920 YouTube Short. Duration is now DYNAMIC - it's set
by how long the Hindi voice narration runs (roughly 18-32 seconds), not a
fixed 5 seconds. Very short Shorts get almost no algorithmic distribution in
2026, so the narration is what gives the video real length and real content.

  [ TOP IMAGE   - Ken Burns zoom/pan animation, full narration length ]
  [ RED BAND    - bold white Hindi title + yellow summary            ]
  [ BOTTOM IMAGE- Ken Burns zoom/pan animation, full narration length ]

Audio = Hindi narration (full volume) + royalty-free background music
(ducked to low volume underneath it).
"""

import os
import random
import textwrap
import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from moviepy.editor import (
    ImageClip, CompositeVideoClip, AudioFileClip, VideoClip,
    CompositeAudioClip, concatenate_videoclips, concatenate_audioclips
)
from moviepy.audio.fx.all import volumex

W, H = 1080, 1920
TOP_H = 650
BOTTOM_H = 650
MID_H = H - TOP_H - BOTTOM_H  # 620

MIN_DURATION = 18.0   # floor - anything shorter gets almost no Shorts distribution in 2026
MAX_DURATION = 32.0   # ceiling - keeps render time and file size sane
NARRATION_TAIL = 1.8  # extra seconds after narration ends, so it doesn't feel cut off

FONT_URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/hind/Hind-Bold.ttf"
FONT_DIR = os.path.join(os.path.dirname(__file__), "..", "assets")
FONT_PATH = os.path.join(FONT_DIR, "Hind-Bold.ttf")


FALLBACK_FONT_URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/notosansdevanagari/NotoSansDevanagari%5Bwdth%2Cwght%5D.ttf"


def ensure_font():
    os.makedirs(FONT_DIR, exist_ok=True)
    if not os.path.exists(FONT_PATH):
        try:
            r = requests.get(FONT_URL, timeout=60)
            r.raise_for_status()
            with open(FONT_PATH, "wb") as f:
                f.write(r.content)
        except Exception:
            r = requests.get(FALLBACK_FONT_URL, timeout=60)
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
    """Solid RED news band: white bold title on top, yellow bold summary below (KK-News style).
    Font size auto-shrinks so long titles never get cut off."""
    title = (title or "आज की बड़ी खबर").strip()
    summary = (summary or "इस खबर से जुड़ी महत्वपूर्ण जानकारी सामने आई है।").strip()

    panel = Image.new("RGB", (W, MID_H), (196, 20, 20))  # solid news-red band

    title_size, summary_size = 68, 40
    max_available_h = MID_H - 40  # leave breathing room top/bottom

    while True:
        title_img = _wrapped_text_image(
            title, font_path, title_size, W - 70, fill="white",
            stroke_width=3, stroke_fill=(90, 0, 0)
        )
        summary_img = _wrapped_text_image(
            summary, font_path, summary_size, W - 110, fill=(255, 221, 0),
            stroke_width=2, stroke_fill=(80, 40, 0)
        )
        total_h = title_img.height + 20 + summary_img.height
        if total_h <= max_available_h or title_size <= 34:
            break
        title_size -= 4
        summary_size -= 2

    start_y = max(6, (MID_H - total_h) // 2)

    panel.paste(title_img, ((W - title_img.width) // 2, start_y), title_img)
    panel.paste(summary_img, ((W - summary_img.width) // 2, start_y + title_img.height + 20), summary_img)
    return panel


def make_breaking_badge(font_path, text="ब्रेकिंग न्यूज़"):
    """Red 'BREAKING NEWS' style ribbon badge, TV-news style - big and bold."""
    font = ImageFont.truetype(font_path, 62)
    dummy = Image.new("RGBA", (10, 10))
    d = ImageDraw.Draw(dummy)
    bbox = d.textbbox((0, 0), text, font=font, stroke_width=3)
    pad_x, pad_y = 48, 24
    w = bbox[2] - bbox[0] + pad_x * 2
    h = bbox[3] - bbox[1] + pad_y * 2

    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w, h], fill=(215, 15, 15, 255))
    # small white square "on-air" dot for extra news feel
    dot_r = 12
    d.ellipse([pad_x - 34, h // 2 - dot_r, pad_x - 34 + dot_r * 2, h // 2 + dot_r], fill="white")
    d.text((pad_x, pad_y - 8), text, font=font, fill="white",
           stroke_width=3, stroke_fill=(110, 0, 0))
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


def make_logo_badge(font_path, line1="NEWS", line2="SUPERNOVA"):
    """Channel logo bug: solid red box, bold white two-line text (like a TV news channel logo)."""
    font1 = ImageFont.truetype(font_path, 36)
    font2 = ImageFont.truetype(font_path, 30)
    dummy = Image.new("RGBA", (10, 10))
    d = ImageDraw.Draw(dummy)

    b1 = d.textbbox((0, 0), line1, font=font1, stroke_width=2)
    b2 = d.textbbox((0, 0), line2, font=font2, stroke_width=1)
    w1, h1 = b1[2] - b1[0], b1[3] - b1[1]
    w2, h2 = b2[2] - b2[0], b2[3] - b2[1]

    pad_x, pad_y, gap = 28, 16, 4
    w = max(w1, w2) + pad_x * 2
    h = h1 + h2 + gap + pad_y * 2

    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w, h], fill=(205, 16, 16, 255))
    d.rectangle([0, 0, w, h], outline="white", width=3)

    d.text(((w - w1) // 2, pad_y - 4), line1, font=font1, fill="white",
           stroke_width=2, stroke_fill=(110, 0, 0))
    d.text(((w - w2) // 2, pad_y + h1 + gap - 2), line2, font=font2, fill="white",
           stroke_width=1, stroke_fill=(110, 0, 0))
    return img


def make_ghost_watermark(font_path, text="NEWS SUPERNOVA", font_size=46, opacity=55):
    """Large, low-opacity watermark text - the classic 'anti-copy' news watermark look."""
    font = ImageFont.truetype(font_path, font_size)
    dummy = Image.new("RGBA", (10, 10))
    d = ImageDraw.Draw(dummy)
    bbox = d.textbbox((0, 0), text, font=font, stroke_width=1)
    pad = 20
    w = bbox[2] - bbox[0] + pad * 2
    h = bbox[3] - bbox[1] + pad * 2

    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((pad, pad - 4), text, font=font, fill=(255, 255, 255, opacity),
           stroke_width=1, stroke_fill=(255, 255, 255, opacity))
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
                  music_path, channel_name, out_path, narration_path=None):
    for path in (top_image_path, bottom_image_path):
        if not os.path.isfile(path) or os.path.getsize(path) == 0:
            raise RuntimeError(f"Invalid image file: {path}")

    title = (title or "आज की बड़ी खबर").strip()
    summary = (summary or "इस खबर से जुड़ी महत्वपूर्ण जानकारी सामने आई है।").strip()

    font_path = ensure_font()

    # ---- Figure out the real video length from the narration's length ----
    narration_audio = None
    if narration_path and os.path.exists(narration_path) and os.path.getsize(narration_path) > 0:
        narration_audio = AudioFileClip(narration_path)
        duration = narration_audio.duration + NARRATION_TAIL
    else:
        duration = MIN_DURATION
    duration = max(MIN_DURATION, min(MAX_DURATION, duration))

    # ---- Middle white text panel (with a subtle breathing pulse) ----
    mid_img = make_middle_panel(title, summary, font_path)
    mid_path = "/tmp/_mid_panel.png"
    mid_img.save(mid_path)
    mid_clip = _breathing_clip(mid_path, W, MID_H, duration).set_position((0, TOP_H))

    # ---- Top & bottom animated image panels (cropped into their boxes) ----
    top_bg = CompositeVideoClip(
        [_kenburns_clip(top_image_path, W, TOP_H, duration, zoom_in=True)],
        size=(W, TOP_H)
    ).set_duration(duration).set_position((0, 0))

    bottom_bg = CompositeVideoClip(
        [_kenburns_clip(bottom_image_path, W, BOTTOM_H, duration, zoom_in=False)],
        size=(W, BOTTOM_H)
    ).set_duration(duration).set_position((0, H - BOTTOM_H))

    # ---- Vignettes: soft dark gradient at the outer edge of each image panel ----
    top_vignette_img = make_vignette(W, 120, top=True)
    top_vignette_path = "/tmp/_vignette_top.png"
    top_vignette_img.save(top_vignette_path)
    top_vignette = ImageClip(top_vignette_path).set_duration(duration).set_position((0, 0))

    bottom_vignette_img = make_vignette(W, 120, top=False)
    bottom_vignette_path = "/tmp/_vignette_bottom.png"
    bottom_vignette_img.save(bottom_vignette_path)
    bottom_vignette = ImageClip(bottom_vignette_path).set_duration(duration).set_position((0, H - 120))

    # ---- Breaking-news style red badge, top-left over the top image (bigger, lower) ----
    badge_img = make_breaking_badge(font_path)
    badge_path = "/tmp/_badge.png"
    badge_img.save(badge_path)
    badge_clip = ImageClip(badge_path).set_duration(duration).set_position((30, 160))

    # ---- Channel logo badges (top-right and bottom-right), KK-News style ----
    words = channel_name.strip().upper().split(maxsplit=1)
    logo_line1 = words[0] if words else "NEWS"
    logo_line2 = words[1] if len(words) > 1 else ""

    logo_img = make_logo_badge(font_path, logo_line1, logo_line2)
    logo_path = "/tmp/_logo.png"
    logo_img.save(logo_path)

    wm_top = (ImageClip(logo_path)
              .set_duration(duration)
              .set_position((W - logo_img.width - 30, 30)))
    wm_bottom = (ImageClip(logo_path)
                 .set_duration(duration)
                 .set_position((W - logo_img.width - 30, H - logo_img.height - 30)))

    # ---- Large low-opacity "ghost" watermarks (2x) - extra anti-copy layer ----
    ghost_img = make_ghost_watermark(font_path, channel_name.strip().upper())
    ghost_path = "/tmp/_ghost.png"
    ghost_img.save(ghost_path)
    ghost_top = (ImageClip(ghost_path)
                 .set_duration(duration)
                 .set_position(("center", TOP_H - ghost_img.height - 40)))
    ghost_bottom = (ImageClip(ghost_path)
                    .set_duration(duration)
                    .set_position(("center", H - BOTTOM_H + 40)))

    # ---- Pulsing red alert border around the whole frame ----
    border_clip = _pulsing_border_clip(W, H, duration)

    # ---- Quick opening flash - grabs attention the instant it appears in feed ----
    flash_clip = _opening_flash_clip(W, H)

    # ---- Compose everything ----
    final = CompositeVideoClip(
        [top_bg, bottom_bg, top_vignette, bottom_vignette, ghost_top, ghost_bottom,
         mid_clip, badge_clip, wm_top, wm_bottom, border_clip, flash_clip],
        size=(W, H)
    ).set_duration(duration)

    # ---- Audio: Hindi narration (full volume) + background music (ducked underneath) ----
    audio_tracks = []
    if narration_audio is not None:
        audio_tracks.append(narration_audio.set_start(0.2))

    if music_path and os.path.exists(music_path):
        music = AudioFileClip(music_path)
        if music.duration >= duration:
            start = random.uniform(0, music.duration - duration)
            music = music.subclip(start, start + duration)
        else:
            loops_needed = int(duration // music.duration) + 1
            music = concatenate_audioclips([music] * loops_needed).subclip(0, duration)
        music = music.fx(volumex, 0.15)  # duck well under the narration
        audio_tracks.append(music)

    if audio_tracks:
        final = final.set_audio(CompositeAudioClip(audio_tracks).set_duration(duration))

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
