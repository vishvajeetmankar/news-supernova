import hashlib, html, json, os, random, re
from pathlib import Path
import feedparser, requests
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
USED = ROOT / "used_titles.json"
RECENT = ROOT / "recent_titles.json"
BASE = "https://news.google.com/rss"
FEEDS = ["?hl=hi&gl=IN&ceid=IN:hi"] + [
    f"/headlines/section/topic/{t}?hl=hi&gl=IN&ceid=IN:hi"
    for t in ("NATION", "WORLD", "BUSINESS", "TECHNOLOGY", "SPORTS", "ENTERTAINMENT")]

def _hash(title): return hashlib.sha256(title.strip().lower().encode("utf-8")).hexdigest()

def _load():   # used_titles.json = sha256 hashes (teri purani repo wala format)
    try:
        d = json.loads(USED.read_text("utf-8")); return d if isinstance(d, list) else []
    except Exception:
        return []

def _recent():  # fuzzy dedupe ke liye last 60 titles (alag file)
    try: return json.loads(RECENT.read_text("utf-8"))
    except Exception: return []

def _tok(s): return set(re.findall(r"[\u0900-\u0963\u0966-\u097F\w]+", s.lower()))   # Devanagari matras ke saath

def _dup(t, seen_hash, recent):
    if _hash(t) in seen_hash: return True
    a = _tok(t)
    return any(len(a & _tok(s)) / max(1, len(a | _tok(s))) > 0.55 for s in recent)

def fetch_news(exclude=()):
    seen, recent = set(_load()), _recent(); feeds = FEEDS[:]; random.shuffle(feeds)
    for f in feeds:
        for e in feedparser.parse(BASE + f).entries[:25]:
            title = re.sub(r"\s+-\s+[^-]+$", "", e.title).encode("utf-8", "ignore").decode("utf-8").strip()
            if not title or title in exclude or _dup(title, seen, recent): continue
            text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", e.get("summary", "")))).strip()
            src = (e.get("source") or {}).get("title", "Google News")
            return {"title": title, "text": text, "source": src, "link": e.link}
    return None

def mark_used(title):   # upload SUCCESS ke baad hi call hota hai
    h = _load(); h.append(_hash(title))
    USED.write_text(json.dumps(h[-300:], ensure_ascii=False, indent=2), "utf-8")
    r = _recent(); r.append(title)
    RECENT.write_text(json.dumps(r[-60:], ensure_ascii=False), "utf-8")

def _save(content, path):
    path.write_bytes(content); Image.open(path).convert("RGB").save(path, "JPEG", quality=92)

def get_images(queries, n, outdir):
    outdir = Path(outdir); outdir.mkdir(parents=True, exist_ok=True); got = []
    key = os.getenv("PEXELS_API_KEY")
    for i, q in enumerate(queries[:n]):
        p = outdir / f"{i}.jpg"
        try:
            if key:
                r = requests.get("https://api.pexels.com/v1/search", headers={"Authorization": key},
                                 params={"query": q, "orientation": "portrait", "per_page": 6}, timeout=60)
                ph = random.choice(r.json()["photos"])
                _save(requests.get(ph["src"]["large2x"], timeout=120).content, p); got.append(str(p)); continue
        except Exception as e:
            print("[img] pexels", e)
        try:  # fallback: generic AI illustration
            u = (f"https://image.pollinations.ai/prompt/{requests.utils.quote(q + ', cinematic generic illustration, no text, no real people')}"
                 f"?width=1080&height=1400&nologo=true&seed={random.randint(1, 9999)}")
            _save(requests.get(u, timeout=240).content, p); got.append(str(p))
        except Exception as e:
            print("[img] pollinations", e)
    if not got:
        p = outdir / "0.jpg"; Image.new("RGB", (1080, 1400), (20, 30, 60)).save(p); got = [str(p)]
    return got
