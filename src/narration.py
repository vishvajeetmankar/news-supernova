"""
Generates the Hindi voice narration for the short.

Primary engine: edge-tts (Microsoft Edge's FREE online neural voices - no API
key, no login). This sounds like a real human news anchor, not the flat
robotic gTTS reading. Falls back to gTTS automatically if edge-tts ever fails
(network hiccup, voice temporarily unavailable, etc.) so the pipeline never
breaks.

On top of that, we don't just read the title+summary flatly - we wrap it in
one of several "anchor script" STYLE VARIANTS (a hook line before the story,
a subscribe call-to-action after it). A different variant is picked at
random every run, so:
  1. Every video sounds like a real news broadcast (hook -> story -> CTA)
  2. No two videos ever have literally the same script structure, which
     also helps avoid YouTube flagging the channel as repetitive/templated.
"""

import os
import random
import asyncio

# ---------------------------------------------------------------------------
# 5 style variants: each has its own hook, its own closing subscribe line,
# and its own voice "personality" (speed/pitch) so the audio itself varies
# too, not just the words.
# ---------------------------------------------------------------------------
STYLE_VARIANTS = [
    {
        "hook": "इस वक़्त की सबसे बड़ी और सनसनीखेज़ खबर सामने आ रही है!",
        "cta": "ऐसी चौंका देने वाली खबरें सबसे पहले जानने के लिए अभी सब्सक्राइब कीजिए न्यूज़ सुपरनोवा को!",
        "rate": "+18%",
        "pitch": "-4Hz",
    },
    {
        "hook": "ब्रेकिंग न्यूज़! अभी-अभी एक बड़ी खबर आई है, ध्यान से सुनिए।",
        "cta": "अगर आपको ये खबर पसंद आई हो, तो न्यूज़ सुपरनोवा को सब्सक्राइब करना बिल्कुल मत भूलिए!",
        "rate": "+15%",
        "pitch": "-6Hz",
    },
    {
        "hook": "देश-दुनिया की सबसे चौंकाने वाली खबर अभी आपके सामने है!",
        "cta": "रोज़ की ताज़ा और सनसनीखेज़ खबरों के लिए अभी सब्सक्राइब कीजिए न्यूज़ सुपरनोवा!",
        "rate": "+20%",
        "pitch": "-3Hz",
    },
    {
        "hook": "सुनिए, इस वक़्त की सबसे बड़ी खबर, जो हर तरफ चर्चा में है।",
        "cta": "ऐसी खबरें सबसे पहले पाने के लिए न्यूज़ सुपरनोवा चैनल को अभी सब्सक्राइब कर लीजिए!",
        "rate": "+16%",
        "pitch": "-5Hz",
    },
    {
        "hook": "अभी-अभी मिली एक बड़ी खबर, जानिए पूरी सच्चाई इस वीडियो में।",
        "cta": "न्यूज़ सुपरनोवा को सब्सक्राइब कीजिए और पाइए ऐसी खबरें हमेशा सबसे पहले!",
        "rate": "+17%",
        "pitch": "-4Hz",
    },
]

# Deep, dramatic female Hindi neural voice (real human-like, not robotic)
VOICE = "hi-IN-SwaraNeural"


def _build_script(title: str, summary: str, variant: dict) -> str:
    title = (title or "").strip()
    summary = (summary or "").strip()
    return f"{variant['hook']} {title}. {summary} {variant['cta']}"


async def _edge_tts_save(text: str, out_path: str, voice: str, rate: str, pitch: str):
    import edge_tts
    communicate = edge_tts.Communicate(text, voice=voice, rate=rate, pitch=pitch)
    await communicate.save(out_path)


def generate_narration(title: str, summary: str, out_path: str,
                        channel_name: str = "News Supernova") -> str:
    """
    Builds a varied anchor-style script (hook + story + subscribe CTA) and
    synthesizes it with a real neural voice. Returns out_path.
    """
    variant = random.choice(STYLE_VARIANTS)
    script = _build_script(title, summary, variant)

    try:
        asyncio.run(_edge_tts_save(script, out_path, VOICE, variant["rate"], variant["pitch"]))
        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            return out_path
        raise RuntimeError("edge-tts produced an empty file")
    except Exception as e:
        print(f"  !! edge-tts failed ({e}), falling back to gTTS...")
        from gtts import gTTS
        tts = gTTS(text=script, lang="hi", slow=False)
        tts.save(out_path)
        return out_path


if __name__ == "__main__":
    generate_narration(
        "केतन की मौत में सिया के रिश्तेदार रहस्य खुलेंगे",
        "केतन की हत्या के पीछे सिया के परिवार की जुड़ाव की बात उठी है। पूरी जानकारी वीडियो में।",
        "/tmp/test_narration.mp3",
    )
    print("Saved /tmp/test_narration.mp3")
