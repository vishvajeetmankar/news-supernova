"""
Uses Groq's free API (very fast Llama models) to REWRITE the news headline in
Claude's... err, in the model's own masaledar Hindi words, plus a punchy 2-3
line summary. We deliberately rewrite (not copy verbatim) to stay clear of
copyright/plagiarism issues.
"""

import os
import json
from groq import Groq

MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")  # check console.groq.com/docs/models if this ever changes


def rewrite_story(raw_title: str) -> dict:
    client = Groq(api_key=os.environ["GROQ_API_KEY"])

    prompt = f"""Tumhe ek trending news headline di ja rahi hai:
{json.dumps(raw_title, ensure_ascii=False)}

Isko dekh kar (verbatim copy MAT karna, apne alfaazon me likhna):
1. Ek naya, masaledar, catchy Hindi title bana jo YouTube Short ke liye ek highlight jaisa lage. Max 8-9 words.
2. Uska 2-3 line ka summary Hindi me likh jo curiosity create kare.
3. 3-4 simple ENGLISH keywords do jo is news se related generic stock-photo search ke liye use ho sakein (jaise "stock market crash graph" ya "cricket stadium celebration") - koi real person ka naam mat daalna.
4. 8-10 YouTube SEO tags do (comma-separated ek hi string me), is specific news topic se directly related - jaise agar news kisi desh/vyakti/ghatna ke baare me hai to uske naam/topic wale tags do, generic "news" jaisे tags kam rakho.
5. 5-6 hashtags do (space-separated ek hi string me, # ke saath), isi news topic se related, jaise #IranNews #Khamenei waghera jaisa specific - generic ke saath specific bhi mix karo.

JSON object ke roop me sirf ye paanch string fields return karo, koi markdown, code fence ya extra text mat do:
{{"title": "...", "summary": "...", "image_keywords": "...", "tags": "...", "hashtags": "..."}}
"""

    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8,
        max_tokens=500,
    )

    text = (resp.choices[0].message.content or "").strip()
    text = text.replace("```json", "").replace("```", "").strip()

    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        data = {}

    title = str(data.get("title") or "").strip()
    summary = str(data.get("summary") or "").strip()
    image_keywords = str(data.get("image_keywords") or "").strip()
    tags = str(data.get("tags") or "").strip()
    hashtags = str(data.get("hashtags") or "").strip()

    # Strip any invalid/undecodable characters (defends against corrupted
    # source text or odd model output reaching the video renderer)
    title = title.encode("utf-8", errors="ignore").decode("utf-8")
    summary = summary.encode("utf-8", errors="ignore").decode("utf-8")
    image_keywords = image_keywords.encode("utf-8", errors="ignore").decode("utf-8")
    tags = tags.encode("utf-8", errors="ignore").decode("utf-8")
    hashtags = hashtags.encode("utf-8", errors="ignore").decode("utf-8")

    # Safety net: never let an empty/malformed AI response reach the video renderer
    if not title:
        title = raw_title.strip()[:90] or "आज की बड़ी खबर"
    if not summary:
        summary = "इस खबर से जुड़ी महत्वपूर्ण जानकारी सामने आई है। पूरी जानकारी वीडियो में।"
    if not image_keywords:
        image_keywords = "india news"
    if not tags:
        tags = "news, breaking news, trending news, india news, hindi news"
    if not hashtags:
        hashtags = "#news #breakingnews #trending #shorts #viral"

    return {
        "title": title,
        "summary": summary,
        "image_keywords": image_keywords,
        "tags": tags,
        "hashtags": hashtags,
    }


if __name__ == "__main__":
    out = rewrite_story("Sensex 500 points gir gaya aaj")
    print(json.dumps(out, ensure_ascii=False, indent=2))
