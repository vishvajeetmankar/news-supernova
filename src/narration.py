"""
Generates a free Hindi voice narration for the short using gTTS (a free,
keyless wrapper around Google Translate's text-to-speech engine).

This is what lets the video run 18-25 seconds instead of 5 - it gives the
short real spoken content, not just static text, which is both required for
YouTube Shorts distribution (very short Shorts get almost no reach) and for
looking like genuine, valuable content rather than a bare template.
"""

from gtts import gTTS


def generate_narration(text: str, out_path: str, lang: str = "hi") -> str:
    text = (text or "").strip()
    if not text:
        text = "यह एक ताज़ा खबर है। पूरी जानकारी के लिए वीडियो देखें।"

    tts = gTTS(text=text, lang=lang, slow=False)
    tts.save(out_path)
    return out_path


if __name__ == "__main__":
    generate_narration(
        "केतन की मौत में सिया के रिश्तेदार रहस्य खुलेंगे। "
        "केतन की हत्या के पीछे सिया के परिवार की जुड़ाव की बात उठी है।",
        "/tmp/test_narration.mp3",
    )
    print("Saved /tmp/test_narration.mp3")
