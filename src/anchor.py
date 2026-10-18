import os, shutil, subprocess, urllib.parse
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent.parent
IMG = ROOT / "assets" / "anchor.png"
XT = ROOT / "xtalker"
PY = os.getenv("XT_PYTHON", str(ROOT / ".venv-xt" / "bin" / "python"))

def make_image(seed=42):
    """Ek baar chala ke assets/anchor.png commit kar de (ya apni AI-generated female face image daal)."""
    p = ("photorealistic portrait of a professional Indian female Hindi TV news anchor, black blazer, facing camera "
         "straight, calm neutral face, mouth closed, soft studio lighting, plain dark navy background, "
         "head and shoulders, sharp focus, 4k")
    u = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(p)}?width=768&height=768&model=flux&seed={seed}&nologo=true"
    r = requests.get(u, timeout=300); r.raise_for_status()
    IMG.parent.mkdir(exist_ok=True); IMG.write_bytes(r.content); print("saved", IMG)

def talk(wav, out):
    """XTalker/SadTalker lip-sync clip. Fail ho to None (studio.py fallback chalayega)."""
    if not ((XT / "inference.py").exists() and Path(PY).exists() and IMG.exists()):
        print("[anchor] xtalker ya anchor.png nahi mila, fallback"); return None
    size, timeout = os.getenv("ANCHOR_SIZE", "256"), int(os.getenv("ANCHOR_TIMEOUT", "3600"))
    res = ROOT / "work" / "xt"; shutil.rmtree(res, ignore_errors=True); res.mkdir(parents=True)
    cmd = [PY, "inference.py", "--driven_audio", str(wav), "--source_image", str(IMG), "--result_dir", str(res),
           "--still", "--preprocess", "crop", "--size", size, "--expression_scale", "1.3", "--cpu"]
    try:
        subprocess.run(cmd, cwd=XT, timeout=timeout, check=True)
        vids = sorted(res.glob("*.mp4"), key=os.path.getmtime)
        if not vids: raise RuntimeError("output mp4 nahi bani")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(vids[-1]), "-an", "-r", "25",
                        "-vf", "scale=830:830:flags=lanczos,unsharp=5:5:0.8", "-pix_fmt", "yuv420p", str(out)], check=True)
        return str(out)
    except Exception as e:
        print("[anchor] fail ->", e); return None

if __name__ == "__main__":
    make_image()
