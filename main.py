"""
Full pipeline, run manually OR by GitHub Actions cron:

  1. Fetch a fresh trending headline (free RSS)
  2. Rewrite it in masaledar Hindi (Groq, free)
  3. Get one AI image (Pollinations, free) + one licensed stock image (Pexels, free)
  4. Render 5-second vertical short with animation, Hindi text, watermark, music
  5. Upload to YouTube (News Supernova channel)

Usage:
    python main.py
"""

import os
import sys
import tempfile
import traceback

# Force safe UTF-8 output so a stray corrupted character anywhere in a news
# title/summary can never crash the logger and hide the real error.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from fetch_news import get_trending_story
from rewrite_news import rewrite_story
from get_images import get_ai_image, get_stock_image
from render_video import render_short, pick_random_music
from upload_youtube import upload_short

CHANNEL_NAME = os.environ.get("CHANNEL_NAME", "News Supernova")


def run_once():
    print("Step 1/5: fetching trending story...")
    story = get_trending_story()
    print("  ->", story["title"])

    print("Step 2/5: rewriting with Groq...")
    rewritten = rewrite_story(story["title"])
    print("  -> title:", rewritten["title"])
    print("  -> summary:", rewritten["summary"])

    with tempfile.TemporaryDirectory() as tmp:
        top_img = os.path.join(tmp, "top.jpg")
        bottom_img = os.path.join(tmp, "bottom.jpg")
        out_video = os.path.join(tmp, "short.mp4")

        print("Step 3/5: fetching images...")
        get_ai_image(rewritten["image_keywords"], top_img)
        get_stock_image(rewritten["image_keywords"], bottom_img)

        print("Step 4/5: rendering video...")
        music = pick_random_music()
        if not music:
            print("  !! WARNING: no music file found in /music folder - uploading with silence.")
        render_short(
            top_image_path=top_img,
            bottom_image_path=bottom_img,
            title=rewritten["title"],
            summary=rewritten["summary"],
            music_path=music,
            channel_name=CHANNEL_NAME,
            out_path=out_video,
        )

        print("Step 5/5: uploading to YouTube...")
        tag_list = [t.strip() for t in rewritten["tags"].split(",") if t.strip()]
        video_id = upload_short(
            video_path=out_video,
            title=rewritten["title"],
            description=rewritten["summary"] + f"\n\nSource: {story.get('source','')}\n\n" + rewritten["hashtags"],
            tags=tag_list,
        )
        print(f"DONE ✅  https://youtube.com/shorts/{video_id}")


if __name__ == "__main__":
    try:
        run_once()
    except Exception:
        print("PIPELINE FAILED ❌", flush=True)
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        sys.exit(1)
