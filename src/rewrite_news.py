"""
Uses Groq's free API (very fast Llama models) to REWRITE the news headline in
Claude's... err, in the model's own masaledar Hindi words, plus a punchy 2-3
line summary. We deliberately rewrite (not copy verbatim) to stay clear of
copyright/plagiarism issues.
"""

import os
import json
from groq import Groq

MODEL = "llama-3.3-70b-versatile"  # free tier on Groq as of writing; check console.groq.com/docs/models


def rewrite_story(raw_title: str) -> dict:
    client = Groq(api_key=os.environ["GROQ_API_KEY"])

    prompt = f"""Tumhe ek trending news headline di ja rahi hai:
"{raw_title}"

Isko dekh kar (verbatim copy MAT karna, apne alfaazon me likhna):
1. Ek naya, masaledar, catchy Hindi title bana jo YouTube Short ke liye ek highlight jaisa lage. Max 8-9 words.
2. Uska 2-3 line ka summary Hindi me likh jo curiosity create kare.
3. 3-4 simple ENGLISH keywords do jo is news se related generic stock-photo search ke liye use ho sakein (jaise "stock market crash graph" ya "cricket stadium celebration") - koi real person ka naam mat daalna.

Sirf neeche diye JSON format me jawaab do, kuch aur likhna hi mat:
{{"title": "...", "summary": "...", "image_keywords": "..."}}
"""

    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8,
        max_tokens=300,
    )

    text = resp.choices[0].message.content.strip()
    text = text.replace("```json", "").replace("```", "").strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # fallback: crude split if model didn't return clean JSON
        data = {"title": raw_title[:40], "summary": text[:150], "image_keywords": "news india"}

    return {
        "title": data.get("title", "").strip(),
        "summary": data.get("summary", "").strip(),
        "image_keywords": data.get("image_keywords", "india news").strip(),
    }


if __name__ == "__main__":
    out = rewrite_story("Sensex 500 points gir gaya aaj")
    print(json.dumps(out, ensure_ascii=False, indent=2))
