# News Supernova — Auto Shorts (100% Free)

Rozana 5 baar (9:00, 9:15, 9:30 subah + 7:00, 7:15 shaam IST), fully automatic
YouTube Short banega aur upload hoga. Sab kuch free tools se, aur kabhi bhi
manually test bhi kar sakte ho.

## Ye kaise kaam karta hai (in short)
1. **News**: Google News RSS (free, public) se trending headline uthata hai
2. **Rewrite**: Groq API (free) se headline + 2-3 line summary apne shabdon me likhta hai — verbatim copy nahi (copyright-safe)
3. **Images**: Ek AI-generated image (Pollinations.ai, free, no key) + ek licensed stock photo (Pexels, free key)
4. **Video**: Python (FFmpeg/MoviePy) se 5-second vertical (1080x1920) short banata hai — top/bottom image Ken Burns zoom animation ke saath, beech me white bg par bold Hindi title+summary, "News Supernova" watermark upar-neeche
5. **Music**: Tumhare `music/` folder me se random royalty-free track ka random 5-sec hissa
6. **Upload**: YouTube Data API (free quota) se seedha tumhare channel par
7. **Schedule**: GitHub Actions (free, 2000 min/month) cron se roz 5 baar apne aap chalta hai — aur "Run workflow" button se kabhi bhi manually chala sakte ho

---

## Setup (ek baar karna hai, ~20-25 minute)

### 1) Repo GitHub par daalo
- Ye poora folder GitHub par ek **naya repository** bana kar push kar do (public ya private, dono chalega)

### 2) Groq API key (free) - news rewrite ke liye
- https://console.groq.com par jao -> sign up -> API Keys -> naya key banao
- Free tier me kaafi requests milti hain, 5/day ke liye bilkul enough

### 3) Pexels API key (free) - stock image ke liye
- https://www.pexels.com/api/ par jao -> sign up -> turant free key milegi

### 4) YouTube API setup (thoda lamba hai, ek baar ka kaam)
1. https://console.cloud.google.com par jao, naya project banao
2. "APIs & Services" -> "Library" -> **YouTube Data API v3** search karke Enable karo
3. "APIs & Services" -> "Credentials" -> "Create Credentials" -> "OAuth client ID"
   - Application type: **Desktop app**
   - Client ID aur Client Secret note kar lo
4. "OAuth consent screen" me apna Google account (jisme News Supernova channel hai) test user me add karo
5. Apne computer par (repo clone karke):
   ```
   pip install google-auth-oauthlib
   set YOUTUBE_CLIENT_ID=xxxx        (Windows: set, Mac/Linux: export)
   set YOUTUBE_CLIENT_SECRET=xxxx
   python src/get_youtube_token.py
   ```
6. Browser khulega -> News Supernova wale Google account se login karo -> allow karo
7. Terminal me ek **refresh token** print hoga - use save kar lo

### 5) Music files daalo
- `music/README.md` follow karo (YouTube Audio Library se 10-15 gaane manually download karke `music/` folder me daal do)

### 6) GitHub Secrets me sab keys daalo
Repo -> Settings -> Secrets and variables -> Actions -> "New repository secret":
- `GROQ_API_KEY`
- `PEXELS_API_KEY`
- `YOUTUBE_CLIENT_ID`
- `YOUTUBE_CLIENT_SECRET`
- `YOUTUBE_REFRESH_TOKEN`

### 7) Bas ho gaya!
- Workflow apne aap roz 5 baar chalega (9:00, 9:15, 9:30 AM + 7:00, 7:15 PM IST)
- Kabhi bhi test karne ke liye: repo -> "Actions" tab -> "News Supernova - Auto Shorts" -> **"Run workflow"** button dabao -> turant chal jayega

---

## Local par test karna (optional)
```bash
pip install -r requirements.txt
cp .env.example .env   # fir .env me apni keys bharo
# .env load karne ke liye:
export $(cat .env | xargs)   # Mac/Linux
python main.py
```

## Important notes
- Upload `privacyStatus` abhi `"public"` set hai (`src/upload_youtube.py`) — testing ke waqt chaho to `"private"` kar lena, phir wapas `"public"` kar dena.
- YouTube free quota me roz ~6 uploads ka space hai — humara 5/day plan aaram se fit hota hai.
- Har cheez (news rewrite, images, video) copyright-safe rakhi gayi hai taaki channel par strike na aaye.
