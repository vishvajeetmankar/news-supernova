import os, shutil, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import json
from src import news, script_ai, voice, studio

ROOT = Path(__file__).resolve().parent; WORK = ROOT / "work"

def upload(path, d, item):
    from src.upload_youtube import upload_short   # tera purana uploader (AI-disclosure ON)
    desc = (f"{d['anchor_full']}\n\n{d['voiceover']}\n\nस्रोत: {item['source']} (Google News)\n\n"
            f"इस वीडियो में AI-जनित एंकर और AI आवाज़ का उपयोग हुआ है।\n\n{' '.join(d['hashtags'])} #shorts #news")
    return upload_short(video_path=str(path), title=d["title"], description=desc, tags=d["tags"])

def main():
    shutil.rmtree(WORK, ignore_errors=True); WORK.mkdir()
    item = news.fetch_news()
    if not item: sys.exit("fresh news nahi mili")
    print("[news]", item["title"])
    d = script_ai.generate(item)
    print("[opener]", repr(d["opener"]), "| tone:", d["tone"])
    print("[script]", json.dumps({k: d[k] for k in ("title", "headline", "anchor_full", "voiceover_full", "tone")}, ensure_ascii=False, indent=1))
    wavA, wavB = voice.synth_parts([d["anchor_full"], d["voiceover_full"]], d["tone"], WORK)
    wavAll = voice.concat(wavA, wavB, WORK / "all.wav")
    mix = voice.add_music(wavAll, WORK / "mix.wav")
    imgs = news.get_images(d["image_queries"], 3, WORK / "img")
    out = studio.build(d, wavA, wavB, wavAll, mix, imgs, WORK / "news.mp4")
    if os.getenv("DRY_RUN") == "true":
        print("DRY_RUN: upload skip"); return
    vid = upload(out, d, item); print(f"DONE https://youtube.com/shorts/{vid}")
    news.mark_used(item["title"]); script_ai.remember(d)

if __name__ == "__main__":
    main()
