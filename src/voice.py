import asyncio, os, random, re, subprocess, time
from pathlib import Path
import requests

LOUD = "[shouting, loud, aggressive female news anchor, high energy] "
TAGS = {"serious": "[firm, loud, serious female news anchor] "}   # baaki sab LOUD
# bass + presence + heavy compression + loud limiter = "chillati anchor" wala punch
MASTER = ("highpass=f=80,equalizer=f=120:t=q:w=1:g=5,equalizer=f=3500:t=q:w=1.2:g=4,"
          "acompressor=threshold=0.05:ratio=6:attack=3:release=60:makeup=4,"
          "loudnorm=I=-11:TP=-1:LRA=7,alimiter=limit=0.95")

def _ff(*a): return subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *a], capture_output=True, text=True)

def _clean(t):
    return re.sub(r"\s+", " ", t.replace("%", " प्रतिशत").replace("₹", "रुपये ").replace("&", " और ")).strip()

def _ok(p):  # silent / too-short audio detector
    try:
        d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                  "default=nw=1:nk=1", p], capture_output=True, text=True).stdout.strip() or 0)
        v = subprocess.run(["ffmpeg", "-i", p, "-af", "volumedetect", "-f", "null", "-"],
                           capture_output=True, text=True).stderr
        m = re.search(r"mean_volume:\s*(-?[\d.]+)", v)
        return d > 1.5 and m is not None and float(m.group(1)) > -40
    except Exception:
        return False

def _fish(text, tone, out):
    key, vid = os.getenv("FISH_API_KEY"), os.getenv("FISH_VOICE_ID")
    if not key or not vid:   # voice ID ke bina male/default voice aa sakti hai, isliye skip
        raise RuntimeError("FISH_API_KEY / FISH_VOICE_ID (female voice) set nahi hai")
    if os.getenv("FISH_TAGS", "1") == "1":
        text = (os.getenv("FISH_TAG") or TAGS.get(tone, LOUD)) + text
    body = {"text": text, "reference_id": vid, "format": "mp3", "latency": "normal",
            "prosody": {"speed": round(random.uniform(1.08, 1.15), 2), "volume": 0}}
    r = requests.post("https://api.fish.audio/v1/tts", json=body, timeout=180,
                      headers={"Authorization": f"Bearer {key}", "model": os.getenv("FISH_MODEL", "s2.1-pro-free")})
    r.raise_for_status(); Path(out).write_bytes(r.content)

def _edge(text, tone, out):   # Swara = female
    import edge_tts
    rate, pitch = {"serious": ("+6%", "+0Hz"), "breaking": ("+20%", "+8Hz")}.get(tone, ("+15%", "+5Hz"))
    asyncio.run(edge_tts.Communicate(text, os.getenv("EDGE_VOICE", "hi-IN-SwaraNeural"),
                                     rate=rate, pitch=pitch, volume="+40%").save(out))

def _gtts(text, tone, out):
    from gtts import gTTS
    gTTS(text, lang="hi").save(out)

def _master(raw, wav):
    _ff("-i", str(raw), "-af", MASTER, "-ar", "44100", "-ac", "1", str(wav))
    if not _ok(str(wav)): raise RuntimeError("mastering ke baad audio kharab")
    return str(wav)

def synth_parts(parts, tone, outdir):
    """Saare parts ek hi engine se (voice consistent). Fish -> Edge(Swara) -> gTTS."""
    outdir = Path(outdir)
    for name, fn, tries in (("fish", _fish, 3), ("edge", _edge, 4), ("gtts", _gtts, 2)):
        outs, good = [], True
        for i, t in enumerate(parts):
            raw = outdir / f"raw_{i}.mp3"; done = False
            for k in range(tries):
                try:
                    fn(_clean(t), tone, str(raw))
                    if _ok(str(raw)): done = True; break
                    print(f"[voice] {name} silent/short (try {k+1})")
                except Exception as e:
                    print(f"[voice] {name} try {k+1}: {e}")
                    if name == "fish" and "FISH_" in str(e): break
                time.sleep(3 * (k + 1))
            if not done: good = False; break
            outs.append(_master(raw, outdir / f"voice_{i}.wav"))
        if good:
            print(f"[voice] engine = {name}"); return outs
    raise RuntimeError("saare TTS engines fail")

def concat(a, b, out):
    _ff("-i", a, "-i", b, "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1", str(out)); return str(out)
