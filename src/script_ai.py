import json, os, random, re
from pathlib import Path
from groq import Groq

ROOT = Path(__file__).resolve().parent.parent
OPEN = ROOT / "used_openers.json"
MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

OPENERS = ["सबसे बड़ी ख़बर...", "इस वक़्त की ट्रेंडिंग न्यूज़...",
           "इसी वक़्त की सबसे बड़ी ख़बर सामने आ रही है...", ""]      # "" = seedhi khabar
CLOSING = "ऐसी ही ट्रेंडिंग न्यूज़ जानने के लिए न्यूज़ सुपरनोवा को सब्सक्राइब और फ़ॉलो कीजिए।"   # fix hai

STYLES = [
    "सीधा धमाका: पहले ही वाक्य में सबसे बड़ी बात",
    "तीखा सवाल: एक ललकारता सवाल, फिर जवाब",
    "आम आदमी पर असर: पहले बताओ इससे किसे फ़र्क़ पड़ेगा",
    "गरजता अंदाज़: छोटे, ज़ोरदार, चोट करने वाले वाक्य",
    "सस्पेंस: पहले अधूरी बात, फिर खुलासा (बिना झूठ के)",
]
SYSTEM = """तुम 'न्यूज़ सुपरनोवा' हिंदी न्यूज़ चैनल की चीफ़ एडिटर और आक्रामक, गरजने वाली प्राइमटाइम महिला एंकर की स्क्रिप्ट राइटर हो।
सख़्त नियम (कोई भी तोड़ना मना है):
1. तथ्य: सिर्फ़ दिए गए SOURCE से। कोई नाम, तारीख़, आँकड़ा, जगह, बयान, वजह, मंशा या नतीजा अपनी तरफ़ से मत जोड़ो। 'क्यों हुआ', 'किसने मजबूर किया', 'आगे क्या होगा' जैसी बातें तभी लिखो जब SOURCE में साफ़ लिखी हों। जानकारी कम हो तो कम बोलो। अटकल मत लगाओ। आरोप को आरोप कहो, साबित बात को साबित।
2. संवेदनशील ख़बरें (मौत, हादसा, अपराध, दंगा): tone 'serious' रखो, सनसनी नहीं, संयमित भाषा।
3. किसी धर्म, जाति, समुदाय, पार्टी या व्यक्ति के ख़िलाफ़ भड़काऊ, पक्षपाती या अपमानजनक भाषा बिल्कुल नहीं।
4. भाषा: बोलचाल की देवनागरी हिंदी। बहुत छोटे, ज़ोरदार, चोट करने वाले वाक्य (6-12 शब्द), जहाँ असर चाहिए वहाँ '!' या '?' लगाओ ताकि एंकर गरजकर बोल सके। '%' की जगह 'प्रतिशत', '₹' की जगह 'रुपये' लिखो।
5. anchor_line में 'सबसे बड़ी ख़बर', 'ट्रेंडिंग न्यूज़', 'इस वक़्त' जैसी शुरुआत कभी मत लिखो (वो कोड जोड़ता है)। कोई emoji, hashtag, markdown, कोष्ठक, स्टेज-डायरेक्शन या 'एंकर:' जैसा लेबल नहीं। सब्सक्राइब/फ़ॉलो/CTA मत बोलो, वो कोड जोड़ेगा।
6. anchor_line: 20-30 शब्द (हुक + मुख्य ख़बर)। voiceover: 30-42 शब्द (पृष्ठभूमि, असर, आगे क्या)। SOURCE में जानकारी कम हो तो छोटी लिखो (anchor_line 14+, voiceover 24+ शब्द), पर कुछ गढ़ो मत। कोई भी संख्या तभी लिखो जब वो SOURCE में हू-ब-हू लिखी हो।
7. आउटपुट सिर्फ़ एक valid JSON object, उसके बाहर कुछ नहीं।"""
SCHEMA = """{
"title": "यूट्यूब टाइटल, 60 अक्षर तक, हिंदी, दमदार पर सच्चा",
"headline": "स्क्रीन पर दिखने वाली सुर्ख़ी, 9 शब्द तक",
"anchor_line": "...",
"voiceover": "...",
"tone": "breaking | serious | positive | sports | entertainment में से एक",
"ticker": ["3 छोटी पंक्तियाँ, 8 शब्द तक, सिर्फ़ SOURCE के तथ्य"],
"tags": ["8 हिंदी/अंग्रेज़ी टैग"],
"hashtags": ["#..." , "4 हैशटैग"],
"image_queries": ["3 English stock-photo queries, generic, बिना असली नामों के"]
}"""

def _state():
    try:
        s = json.loads(OPEN.read_text("utf-8"))
        return s if isinstance(s, dict) else {"starts": s, "last": ""}
    except Exception:
        return {"starts": [], "last": ""}

def remember(d):
    s = _state()
    s["starts"] = (s["starts"] + [" ".join(d["anchor_line"].split()[:4])])[-40:]; s["last"] = d["opener"]
    OPEN.write_text(json.dumps(s, ensure_ascii=False), "utf-8")

def _parse(raw):
    try: return json.loads(raw)
    except Exception:
        m = re.search(r"\{.*\}", raw or "", re.S)
        if not m: raise ValueError("JSON नहीं मिला")
        return json.loads(m.group(0))

BAN_START = ("सबसे बड़ी", "इस वक़्त", "इसी वक़्त", "इस वक्त", "इसी वक्त", "ट्रेंडिंग")

def _nums(t):   # 2+ digit numbers (commas hata ke); 1-digit ignore (ek/do jaise shabd)
    return {n.replace(",", "") for n in re.findall(r"\d[\d,]*\d|\d", t) if len(n.replace(",", "")) >= 2}

def _check(d, src, opener=""):
    need = ["title", "headline", "anchor_line", "voiceover", "tone", "ticker", "tags", "hashtags", "image_queries"]
    miss = [k for k in need if not d.get(k)]
    if miss: return f"ये keys missing हैं: {miss}"
    for k in ("ticker", "tags", "hashtags", "image_queries"):
        if not isinstance(d[k], list): return f"{k} list होनी चाहिए"
    a, v = len(d["anchor_line"].split()), len(d["voiceover"].split())
    if not 12 <= a <= 40: return f"anchor_line {a} शब्द की है, 20-30 चाहिए"
    if not 20 <= v <= 56: return f"voiceover {v} शब्द का है, 30-42 चाहिए"
    al = d["anchor_line"].strip()
    if al.startswith(BAN_START): return "anchor_line में opener जैसी शुरुआत मत दोहराओ, सीधे ख़बर से शुरू करो"
    if len(d["headline"].split()) > 10: return "headline 9 शब्द से छोटी रखो"
    body = " ".join([d["anchor_line"], d["voiceover"], d["headline"], d["title"], *map(str, d["ticker"])])
    if re.search(r"[*#_\[\]{}<>\U0001F000-\U0001FFFF\u2600-\u27BF\u2B00-\u2BFF]", body): return "markdown/emoji/hashtag मत डालो"
    sn = src.replace(",", "")
    bad = {n for n in _nums(body) if n not in _nums(src) and n not in sn}
    if bad: return f"ये अंक SOURCE में नहीं हैं: {sorted(bad)}, इन्हें हटाओ"
    if d["tone"] not in ("breaking", "serious", "positive", "sports", "entertainment"): d["tone"] = "serious"
    return ""

def _verify(client, src, d):
    """Doosra pass: kaun se daave SOURCE me nahi hain."""
    q = (f"SOURCE:\n{src}\n\nस्क्रिप्ट:\n{d['anchor_line']} {d['voiceover']}\n\n"
         "स्क्रिप्ट के वो दावे बताओ जो SOURCE में साफ़ नहीं लिखे (वजह, मंशा, आँकड़े, नाम, भविष्यवाणी, नतीजा)। "
         'सिर्फ़ JSON: {"unsupported": ["..."]}। कुछ न हो तो खाली list।')
    try:
        r = client.chat.completions.create(
            model=MODEL, temperature=0, max_tokens=2000, response_format={"type": "json_object"},
            extra_body={"reasoning_effort": "low"},
            messages=[{"role": "system", "content": "तुम सख़्त फ़ैक्ट-चेकर हो। सिर्फ़ JSON दो।"}, {"role": "user", "content": q}])
        u = _parse(r.choices[0].message.content or "{}").get("unsupported", [])
        return [str(x) for x in u if str(x).strip()]
    except Exception as e:
        print("[verify] skip:", e); return []

def generate(item):
    client = Groq(api_key=os.environ["GROQ_API_KEY"], timeout=180)
    s = _state(); opener = random.choice([o for o in OPENERS if o != s["last"]])
    src = f"शीर्षक: {item['title']}\nस्रोत: {item['source']}\nविवरण: {item['text'][:1200]}"
    op_note = (f"anchor_line से पहले कोड ये opener जोड़ेगा: '{opener}'। उसे दोहराओ मत, वाक्य उससे सहज जुड़ना चाहिए।"
               if opener else "कोई opener नहीं है। anchor_line सीधे ख़बर के धमाके से शुरू करो।")
    user = (f"इस बार का स्टाइल: {random.choice(STYLES)}\n{op_note}\n"
            f"इन शुरुआतों से बचो (हाल में इस्तेमाल हुईं): {s['starts'][-15:]}\n\nSOURCE:\n{src}\n\n"
            f"सिर्फ़ इस JSON schema में जवाब दो:\n{SCHEMA}")
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
    err = ""
    for i in range(5):
        r = client.chat.completions.create(
            model=MODEL, messages=msgs, temperature=0.7, max_tokens=5000,
            response_format={"type": "json_object"}, extra_body={"reasoning_effort": "low"})
        raw = r.choices[0].message.content or ""
        try:
            d = _parse(raw); err = _check(d, src, opener)
            if not err:
                bad = _verify(client, src, d)
                if bad: err = f"ये दावे SOURCE में नहीं हैं: {bad}। इन्हें हटाओ या SOURCE के हिसाब से लिखो"
        except Exception as e:
            d, err = None, f"JSON टूटा: {e}"
        if not err: break
        print(f"[groq] retry {i+1}: {err}")
        msgs += [{"role": "assistant", "content": raw or "{}"},
                 {"role": "user", "content": f"ग़लती: {err}। सुधारकर दोबारा सिर्फ़ JSON दो।"}]
    else:
        raise RuntimeError(f"valid script nahi bani: {err}")
    d["opener"] = opener
    d["anchor_full"] = (opener + " " + d["anchor_line"].strip()).strip()
    d["voiceover_full"] = d["voiceover"].strip() + " " + CLOSING
    return d
