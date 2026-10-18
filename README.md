# News Supernova: AI Anchor Edition

Roz 5 Hindi news shorts (~30 sec): AI female anchor bolti hai (hook + headline), phir images par voiceover, end me fix subscribe line.
Sab free tools par, GitHub Actions me chalta hai.

## 1. Pipeline (main.py)
| # | Step | File | Kya hota hai |
|---|------|------|--------------|
| 1 | News | src/news.py | Google News RSS (7 feeds random), fuzzy dedupe `used_titles.json` se |
| 2 | Script | src/script_ai.py | Groq `openai/gpt-oss-120b`, strict Hindi prompt, JSON, 5 retries, validation |
| 3 | Voice | src/voice.py | Fish Audio S2 (female voice ID) -> edge-tts Swara -> gTTS, silence check, loud mastering |
| 4 | Anchor | src/anchor.py | XTalker (SadTalker) se lip-sync, sirf anchor wale ~10 sec par. Fail = still-anchor fallback |
| 5 | Images | src/news.py | Pexels (free key) -> Pollinations fallback -> gradient |
| 6 | Render | src/studio.py | MoviePy 1080x1920, lower-third, captions, ticker, badge |
| 7 | Upload | src/upload_youtube.py | TERI PURANI FILE (`upload_short`, is zip me nahi hai), AI-disclosure ON |
| 8 | Music | src/studio.py | Tere `music/` folder se random slice, volume 0.12 (`MUSIC_VOL` env se badlo, `0` = band) |

## 2. Video structure (~30 sec)
- 0 - ~12s: **Anchor scene.** Opener + hook + khabar. Upar story screen, neeche AI anchor.
- ~12 - 30s: **Voiceover scene.** 3 images (Ken Burns + crossfade), detail + fix ending.
- Fix ending: "ऐसी ही ट्रेंडिंग न्यूज़ जानने के लिए न्यूज़ सुपरनोवा को सब्सक्राइब और फ़ॉलो कीजिए।"
- Opener (code chunta hai, LLM nahi): "सबसे बड़ी ख़बर..." / "इस वक़्त की ट्रेंडिंग न्यूज़..." / "इसी वक़्त की सबसे बड़ी ख़बर सामने आ रही है..." / blank (seedhi khabar). Lagataar do baar same nahi.

## 3. Voice ("chillati anchor") kaise banti hai
1. Script: chhote, garajte vakya, `!` `?` (prompt me force).
2. Fish tag: `[shouting, loud, aggressive female news anchor, high energy]`, speed 1.08-1.15.
3. ffmpeg mastering: bass +5dB, presence +4dB, compressor 6:1, loudnorm -11 LUFS, limiter.
4. Maut/hadsa/crime = tone `serious` -> kam chillana (jaan-boojhkar).
5. Female-only: `FISH_VOICE_ID` nahi to Fish skip, seedha Swara.
Tuning: `FISH_TAG` (custom tag), `FISH_TAGS=0` (tag awaaz me bol de to), `EDGE_VOICE`, MASTER string (voice.py) me loudnorm `I=-11` ko `-14` karke thoda naram karo.

## 4. Setup (tere repo `news-supernova` ke upar drop-in)
1. Purani files delete: `git rm -f --ignore-unmatch src/fetch_news.py src/get_images.py src/rewrite_news.py src/narration.py src/render_video.py`.
   **Rakho:** `src/upload_youtube.py`, `src/get_youtube_token.py`, `src/test_youtube_auth.py`, `music/`, `.env.example`.
2. Zip ke andar ki files repo me copy karo (same-name overwrite: `main.py`, `requirements.txt`, `.gitignore`, `README.md`, `.github/workflows/shorts_automation.yml`). Workflow ka naam purane jaisa hi hai, isliye double run nahi hoga.
3. Anchor chehra: `pip install requests && python -m src.anchor` -> `assets/anchor.png`. Pasand na aaye to seed badlo ya apni AI-generated female face (front-facing, mouth closed, 768x768) daalo. Commit karo.
4. Fish Audio: fish.audio par API key banao. Library me **female Hindi** energetic voice dhundo, uska ID copy karo.
5. GitHub Secrets me **naye 2 add karo:** `FISH_API_KEY`, `FISH_VOICE_ID`. Purane (`GROQ_API_KEY`, `PEXELS_API_KEY`, `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN`) waise hi rehne do.
6. Repo **public** rakho (private me 2000 min/month, 5 videos/day ke liye kam).
7. Push -> Actions -> "News Supernova - Auto Shorts" -> Run workflow -> `dry_run=true`. `news-video` artifact me `news.mp4` dekho, log me `[voice] engine = fish` dekho.
8. Sab theek to `dry_run=false` ya schedule chalne do.

Dedupe: `used_titles.json` ka purana hash format waise hi chalta hai (naya `recent_titles.json` sirf milti-julti khabron ke liye). Ab title tabhi "used" hota hai jab upload **successful** ho.

## 5. Schedule
Cron IST 8:30, 8:45, 9:00, 18:30, 18:45. Video banne me ~25-40 min lagte hain, isliye publish 9:00-9:30 / 19:00-19:15 ke aas-paas hoga. Exact time chahiye to cron aur pehle karo.

## 6. Timeouts / limits
Job 300 min, anchor 3600 sec (`ANCHOR_TIMEOUT`), Groq/Fish calls 180 sec, Groq 5 retries, Fish 3 + Edge 4 + gTTS 2 tries.

## 7. Quality knobs
- `ANCHOR_SIZE=512` (env): chehra sharp, par 3-4x slow.
- `--still` hatao (anchor.py): zyada head movement, par artifacts.
- `ANCHOR_TIMEOUT` ghatao agar jaldi fallback chahiye.

## 8. Troubleshooting
| Dikkat | Kya karo |
|--------|----------|
| XTalker setup fail | Actions log dekho. xtalker/requirements.txt ya scripts/download_models.sh ka naam alag ho sakta hai. Python 3.10 + torch 2.0.0 pinned rakho |
| Anchor bohot slow | Normal hai (CPU). Fallback chalega. Time log me dekho |
| Awaaz Fish se nahi aa rahi | Log: `[voice] fish try..`. `FISH_VOICE_ID` check, free tier ka rate limit. Edge Swara apne aap aayegi |
| Tag awaaz me bol raha | `FISH_TAGS=0` |
| Script baar-baar reject | Log `[groq] retry`. Source me jankari kam hogi, ya number hallucination guard laga hoga |
| Hindi text toota-phoota | `fonts-noto-core libraqm0 libfribidi0` install hona chahiye, ya `FONT_PATH` set karo |
| git push conflict | Workflow me rebase retry hai |

## 9. Risks (dhyan rakho)
- **License:** XTalker repo ka disclaimer commercial use mana karta hai. Monetization se pehle SadTalker/XTalker license khud check karo.
- **Fish free tier:** koi uptime guarantee nahi, data model improve me use ho sakta hai. Isiliye fallback chain hai.
- **Facts:** code script ke har number ko source se match karta hai, phir bhi pehle kuch videos upload se pehle khud dekho.
- **YouTube policy:** roz 5 template videos "inauthentic content" me aa sakte hain. AI-disclosure ON rakho, script/images har baar alag rakho.
- **Music:** `music/` ke gaano ke naam me "No Copyright" likha hai, par ye YouTube creators ke videos se liye lagte hain. Unka license ek baar khud check kar lo, ya YouTube Audio Library ke gaane rakho (`music/README.md` dekho).
- **Source credit:** description me Google News / source naam jata hai.

## 10. Aage ke upgrades (optional)
Background music (royalty-free), 2 anchor poses, Hindi TTS A/B test (Fish voices), thumbnails, analytics se best opener pehchanna.
