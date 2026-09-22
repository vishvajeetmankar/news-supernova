"""
Two images per short:
  1. TOP image    -> AI-generated via Pollinations.ai (100% free, no API key, no login)
  2. BOTTOM image -> Real photo from Pexels (free API key, fully licensed for
                      commercial/YouTube use, no attribution legally required)
"""

import os
import time
import random
import requests

POLLINATIONS_URL = "https://image.pollinations.ai/prompt/{prompt}"


def get_ai_image(keywords: str, out_path: str, width=1080, height=1350):
    """Free AI image generation - no key needed."""
    prompt = requests.utils.quote(f"{keywords}, photojournalism style, news graphic, no text, high detail")
    seed = random.randint(1, 999999)
    url = f"{POLLINATIONS_URL.format(prompt=prompt)}?width={width}&height={height}&seed={seed}&nologo=true"

    for attempt in range(3):
        r = requests.get(url, timeout=60)
        if r.status_code == 200 and len(r.content) > 5000:
            with open(out_path, "wb") as f:
                f.write(r.content)
            return out_path
        time.sleep(2)

    raise RuntimeError("Pollinations AI image generation failed after retries")


def get_stock_image(keywords: str, out_path: str):
    """Free, licensed stock photo from Pexels (no copyright issue)."""
    api_key = os.environ["PEXELS_API_KEY"]
    headers = {"Authorization": api_key}
    params = {"query": keywords, "per_page": 10, "orientation": "portrait"}

    r = requests.get("https://api.pexels.com/v1/search", headers=headers, params=params, timeout=30)
    r.raise_for_status()
    photos = r.json().get("photos", [])

    if not photos:
        # fallback to a generic safe query
        params["query"] = "india news"
        r = requests.get("https://api.pexels.com/v1/search", headers=headers, params=params, timeout=30)
        photos = r.json().get("photos", [])

    if not photos:
        raise RuntimeError("No Pexels photo found even with fallback query")

    chosen = random.choice(photos)
    img_url = chosen["src"]["portrait"]
    img_data = requests.get(img_url, timeout=60).content
    with open(out_path, "wb") as f:
        f.write(img_data)
    return out_path


if __name__ == "__main__":
    get_ai_image("stock market crash graph", "/tmp/top.jpg")
    get_stock_image("stock market", "/tmp/bottom.jpg")
    print("done")
