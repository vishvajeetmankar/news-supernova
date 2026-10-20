import asyncio, os, random, re, subprocess, time
from pathlib import Path
import requests

LOUD = "[shouting, loud, aggressive female news anchor, high energy] "
TAGS = {"serious": "[firm, loud, serious female news anchor] "}   # baaki sab LOUD
# bass + presence + heavy compression + loud limiter = "chillati anchor" wala punch
EQ = ("highpass=f=75,equalizer=f=140:t=q:w=1:g=3.5,equalizer=f=300:t=q:w=1.2:g=-1.5,"      # bass/body (high-bass), boxiness kam
      "equalizer=f=3600:t=q:w=1.5:g=-2.5,equalizer=f=6500:t=q:w=1.2:g=-2,lowpass=f=12000,"    # shrill/harsh kam
      "acompressor=threshold=0.09:ratio=3:attack=8:release=120:makeup=2,"
      "loudnorm=I=-14:TP=-1.5:LRA=9")

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
            "prosody": {"speed": round(random.uniform(1.00, 1.06), 2), "volume": 0}}
    r = requests.post("https://api.fish.audio/v1/tts", json=body, timeout=180,
                      headers={"Authorization": f"Bearer {key}", "model": os.getenv("FISH_MODEL", "s2.1-pro-free")})
    r.raise_for_status(); Path(out).write_bytes(r.content)

def _edge(text, tone, out):   # Swara = female
    import edge_tts
    rate, pitch = {"serious": ("+2%", "-4Hz"), "breaking": ("+10%", "-1Hz")}.get(tone, ("+6%", "-3Hz"))
    asyncio.run(edge_tts.Communicate(text, os.getenv("EDGE_VOICE", "hi-IN-SwaraNeural"),
                                     rate=rate, pitch=pitch, volume="+25%").save(out))

def _gtts(text, tone, out):
    from gtts import gTTS
    gTTS(text, lang="hi").save(out)

_RB = None
def _has_filter(name):
    global _RB
    if _RB is None:
        _RB = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    return f" {name} " in _RB

def _master(raw, wav):
    """Pitch thoda neeche (awaaz bharee, kam shrill) + EQ + compress + loudness. Chain fail ho to saada chain."""
    st = float(os.getenv("VOICE_PITCH", "-2"))                      # semitones; 0 = band
    pre = []
    if abs(st) > 0.05:
        if _has_filter("rubberband"): pre.append(f"rubberband=pitch={2 ** (st / 12):.4f}:formant=preserved")
        else: pre.append(f"asetrate={int(44100 * 2 ** (st / 12))},aresample=44100,atempo={2 ** (-st / 12):.4f}")
    chains = []
    if _has_filter("deesser"): chains.append(",".join(pre + ["deesser=i=0.35:f=0.5", EQ]))
    chains.append(",".join(pre + [EQ])); chains.append(EQ)
    for ch in chains:
        r = _ff("-i", str(raw), "-af", ch, "-ar", "44100", "-ac", "1", str(wav))
        if _ok(str(wav)): return str(wav)
        print("[voice] master chain fail:", (r.stderr or "")[-160:])
    raise RuntimeError("mastering ke baad audio kharab")

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

def _dur(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(p)],
                                capture_output=True, text=True).stdout.strip() or 0)

def add_music(voice_wav, out_wav, music_dir=None):
    """music/ folder ka random gaana, random hissa. Awaaz ke neeche sunai deta hai (voice bolte waqt dabta hai)."""
    music_dir = Path(music_dir or Path(__file__).resolve().parent.parent / "music")
    lufs = float(os.getenv("MUSIC_LUFS", "-24"))                # awaaz ~ -14 LUFS; music usse ~10 dB neeche
    tr = [f for f in music_dir.iterdir() if f.suffix.lower() in (".mp3", ".wav", ".m4a")] if music_dir.exists() else []
    if not tr or lufs <= -60:
        return str(voice_wav)
    T = _dur(voice_wav) + 0.6
    for track in random.sample(tr, len(tr)):
        try:
            ss = random.uniform(0, max(0.0, _dur(track) - T - 1))
            fc = (f"[1:a]apad=pad_dur=0.6,asplit=2[v1][v2];"
                  f"[0:a]loudnorm=I={lufs}:TP=-2:LRA=11,aresample=44100,atrim=0:{T:.2f},asetpts=PTS-STARTPTS,afade=t=in:d=0.4,afade=t=out:st={T-1.2:.2f}:d=1.2[m];"
                  f"[m][v1]sidechaincompress=threshold=0.03:ratio=3:attack=20:release=500:makeup=1[duck];"
                  f"[duck][v2]amix=inputs=2:normalize=0:duration=longest,alimiter=limit=0.97")
            r = _ff("-stream_loop", "-1", "-ss", f"{ss:.2f}", "-t", f"{T + 6:.2f}", "-i", str(track), "-i", str(voice_wav), "-filter_complex", fc, "-t", f"{T:.2f}",
                    "-ar", "44100", "-ac", "1", str(out_wav))
            if _ok(str(out_wav)):
                print(f"[music] {track.name[:40]} lufs={lufs}"); return str(out_wav)
            print("[music] mix fail:", (r.stderr or "")[-200:])
        except Exception as e:
            print("[music] skip:", e)
    return str(voice_wav)
